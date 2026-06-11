"""The normative event loop (DESIGN.md §3).

Deterministic heart of the project: consumes (params, event_stream) and
produces fills, declines (replay channel), the jump log, and terminal
state. All price/time arithmetic in integer ticks/µs; no RNG anywhere.

Two output channels (DESIGN.md §3): the censored public feed is exactly
``fills`` + ``quotes`` (what live play and bots may see); the full log
adds ``declines`` and ``jumps`` (unlocked for replay only).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .events import ArrivalEvent, Event, JumpEvent, QuoteEvent
from .params import SimParams


class EngineError(ValueError):
    """The engine was fed an invalid event or stream (fail loudly, §6.3-4)."""


def noise_accept_prob(bid: int, ask: int, delta0: float) -> float:
    """f(h) = exp(-h/delta0) with h = (ask-bid)/2 ticks (DESIGN.md §1.3)."""
    return math.exp(-(ask - bid) / (2.0 * delta0))


@dataclass(frozen=True)
class Fill:
    t_us: int
    side: str  # customer side: "buy" = customer buys at the ask (dealer sells)
    price: int
    v_at_fill: int
    trader: str
    bid: int  # dealer quotes standing at the fill (needed by scoring §2.2)
    ask: int

    @property
    def q(self) -> int:
        """Dealer position change (§0): -1 on customer buy, +1 on customer sell."""
        return -1 if self.side == "buy" else +1


@dataclass(frozen=True)
class Decline:
    t_us: int
    trader: str
    side_intent: str | None  # None for informed (their side is endogenous, D5)
    reason: str  # "v_inside_quotes" | "balked_at_spread"


@dataclass
class RoundResult:
    params: SimParams
    fills: list = field(default_factory=list)
    declines: list = field(default_factory=list)
    jumps: list = field(default_factory=list)  # JumpEvents, for V(t) lookups
    quotes: list = field(default_factory=list)  # QuoteEvents as applied
    v_terminal: int = 0
    cash: int = 0
    inventory: int = 0


class Engine:
    """Apply events one at a time; §3 semantics exactly.

    ``apply`` returns the Fill or Decline an arrival produced (None for
    quote/jump events) so the bot harness can fire on_fill callbacks.
    """

    def __init__(self, params: SimParams):
        self.params = params
        self.v = params.v0
        self.quotes: tuple[int, int] | None = None
        self.cash = 0
        self.inventory = 0
        self._last_t = -1
        self._fills: list[Fill] = []
        self._declines: list[Decline] = []
        self._jumps: list[JumpEvent] = []
        self._quote_log: list[QuoteEvent] = []
        self._finalized = False

    def apply(self, ev: Event) -> Fill | Decline | None:
        if self._finalized:
            raise EngineError("engine already finalized")
        if ev.t_us <= self._last_t:
            raise EngineError(
                f"timestamps must be strictly increasing: {ev.t_us} after {self._last_t} (§0 rule 2)"
            )
        if not (0 <= ev.t_us < self.params.round_us):
            raise EngineError(f"t_us={ev.t_us} outside [0, {self.params.round_us})")
        self._last_t = ev.t_us

        if isinstance(ev, QuoteEvent):
            if ev.ask < ev.bid + 1:
                raise EngineError(f"quote at {ev.t_us}: ask must be >= bid + 1")
            self.quotes = (ev.bid, ev.ask)
            self._quote_log.append(ev)
            return None

        if isinstance(ev, JumpEvent):
            if ev.size == 0:
                raise EngineError(f"jump at {ev.t_us}: size must be nonzero")
            self.v += ev.size
            self._jumps.append(ev)
            return None

        if isinstance(ev, ArrivalEvent):
            if self.quotes is None:
                raise EngineError(f"arrival at {ev.t_us} with no quote set (§1.2)")
            bid, ask = self.quotes
            if ev.trader == "informed":
                # Strict inequalities; ties decline (§1.3).
                if ask < self.v:
                    return self._fill(ev.t_us, "buy", ask, "informed", bid, ask)
                if bid > self.v:
                    return self._fill(ev.t_us, "sell", bid, "informed", bid, ask)
                return self._decline(ev.t_us, "informed", None, "v_inside_quotes")
            # noise: accepts iff u_accept < f(h) (§1.3)
            if ev.u_accept < noise_accept_prob(bid, ask, self.params.delta0):
                price = ask if ev.side_intent == "buy" else bid
                return self._fill(ev.t_us, ev.side_intent, price, "noise", bid, ask)
            return self._decline(ev.t_us, "noise", ev.side_intent, "balked_at_spread")

        raise EngineError(f"unknown event {ev!r}")

    def _fill(self, t_us, side, price, trader, bid, ask) -> Fill:
        f = Fill(t_us, side, price, self.v, trader, bid, ask)
        self.cash -= f.q * price
        self.inventory += f.q
        self._fills.append(f)
        return f

    def _decline(self, t_us, trader, side_intent, reason) -> Decline:
        d = Decline(t_us, trader, side_intent, reason)
        self._declines.append(d)
        return d

    def finalize(self) -> RoundResult:
        self._finalized = True
        return RoundResult(
            params=self.params,
            fills=self._fills,
            declines=self._declines,
            jumps=self._jumps,
            quotes=self._quote_log,
            v_terminal=self.v,
            cash=self.cash,
            inventory=self.inventory,
        )


def run_stream(params: SimParams, events: list) -> RoundResult:
    """Replay mode: consume a complete (vector-style) stream."""
    eng = Engine(params)
    for ev in events:
        eng.apply(ev)
    return eng.finalize()
