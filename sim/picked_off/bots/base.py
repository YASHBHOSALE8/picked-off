"""Common bot interface and harness (DESIGN.md §4.1).

The harness splices bot quote decisions into the engine's event loop as
quote events stamped decision time + 1 µs (the D11 injection rule; the
generator's §6.3-5 timestamp hygiene guarantees the slot is free, so the
engine's strict-monotonicity assertion never fires). on_tick fires at
t = k * TICK_GRID_US for k = 1..(round_us/TICK_GRID_US - 1); on_start
covers t = 0. Bots receive only the public feed: their own fills (time,
side, price) and the clock — never V, trader types, declines, or the raw
stream. The same exogenous stream is replayed for every bot (common
random numbers, §5).

Deterministic intra-timestamp order: a pending injected quote event is
applied before a tick callback at the same microsecond (can only happen
when a fill lands at k*TICK_GRID_US - 1; no arrival can occur before the
next quote applies either way, so outcomes are unaffected).
"""

from __future__ import annotations

import heapq
from typing import Protocol

import numpy as np

from ..engine import Engine, Fill, RoundResult
from ..events import ArrivalEvent, JumpEvent, QuoteEvent, validate_stream
from ..params import TICK_GRID_US, SimParams


class Bot(Protocol):
    def on_start(self, params: SimParams) -> tuple[int, int]: ...  # -> (bid, ask)
    def on_fill(self, t_us: int, side: str, price: int) -> tuple[int, int]: ...
    def on_tick(self, t_us: int) -> tuple[int, int]: ...


_PRIO_QUOTE, _PRIO_EXO, _PRIO_TICK = 0, 1, 2


def _tick_int(value, what: str) -> int:
    """Bots must return integer-tick quotes (§0 rule 1); fail loudly rather
    than silently truncating a float (np.integer is accepted)."""
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"bot returned non-integer {what}: {value!r}")
    return int(value)


def run_bot(params: SimParams, exo_events: list, bot: Bot) -> RoundResult:
    """Run one round: exogenous stream (jumps/arrivals ONLY) + live bot quotes."""
    for ev in exo_events:
        if isinstance(ev, QuoteEvent):
            raise ValueError("harness streams must not contain quote events (§4.1)")
        if not isinstance(ev, (JumpEvent, ArrivalEvent)):
            raise ValueError(f"not an exogenous event: {ev!r}")
    # Fail loudly on malformed streams (§0 rule 2 / §6.3-4): the heap would
    # otherwise silently re-sort a non-monotone stream into a valid run, and
    # hygiene violations (§6.3-5) would only surface as sporadic collisions.
    validate_stream(exo_events, params.round_us, require_opening_quote=False)
    prev_t = None
    for ev in exo_events:
        if ev.t_us <= 1 or ev.t_us % TICK_GRID_US in (0, 1) or (
            prev_t is not None and ev.t_us - prev_t < 2
        ):
            raise ValueError(f"exogenous stream violates §6.3-5 hygiene at t_us={ev.t_us}")
        prev_t = ev.t_us

    eng = Engine(params)
    heap: list = []
    seq = 0

    def push(t_us: int, prio: int, payload) -> None:
        nonlocal seq
        heapq.heappush(heap, (t_us, prio, seq, payload))
        seq += 1

    for ev in exo_events:
        push(ev.t_us, _PRIO_EXO, ev)
    # Every grid point strictly inside (0, round_us); ceil-division so a
    # non-multiple round length still gets its last in-round tick.
    for k in range(1, -(-params.round_us // TICK_GRID_US)):
        push(k * TICK_GRID_US, _PRIO_TICK, None)

    bid, ask = bot.on_start(params)
    bid, ask = _tick_int(bid, "bid"), _tick_int(ask, "ask")
    eng.apply(QuoteEvent(0, bid, ask))
    current = (bid, ask)

    def inject(decision_t: int, quotes: tuple[int, int]) -> None:
        nonlocal current
        quotes = (_tick_int(quotes[0], "bid"), _tick_int(quotes[1], "ask"))
        if quotes == current:
            return  # idempotent re-quote; nothing to splice
        t_q = decision_t + 1  # D11: decision time + 1 µs
        if t_q >= params.round_us:
            return  # round is over before the quote could take effect
        push(t_q, _PRIO_QUOTE, QuoteEvent(t_q, quotes[0], quotes[1]))
        current = quotes

    while heap:
        t_us, prio, _, payload = heapq.heappop(heap)
        if prio == _PRIO_QUOTE:
            eng.apply(payload)
        elif prio == _PRIO_EXO:
            outcome = eng.apply(payload)
            if isinstance(outcome, Fill):
                inject(t_us, bot.on_fill(t_us, outcome.side, outcome.price))
        else:  # tick
            inject(t_us, bot.on_tick(t_us))

    return eng.finalize()
