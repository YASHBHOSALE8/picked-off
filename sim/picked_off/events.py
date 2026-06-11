"""Event types and stream parsing/validation (DESIGN.md §6.2, §0).

Pure data layer: no simulation logic, no randomness. Fails loudly on any
malformed stream per DESIGN.md §6.3 rule 4 — a malformed vector is a bug,
not an input to tolerate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


class StreamError(ValueError):
    """A stream or event violates the DESIGN.md §6.2 schema."""


@dataclass(frozen=True)
class QuoteEvent:
    t_us: int
    bid: int
    ask: int


@dataclass(frozen=True)
class JumpEvent:
    t_us: int
    size: int


@dataclass(frozen=True)
class ArrivalEvent:
    t_us: int
    trader: str  # "informed" | "noise"
    side_intent: Optional[str]  # "buy" | "sell" | None; non-null iff noise
    u_accept: Optional[float]  # [0, 1) | None; non-null iff noise


Event = Union[QuoteEvent, JumpEvent, ArrivalEvent]


def _strict_int(value, what: str) -> int:
    # bool is a subclass of int; JSON true/false must not pass as integers.
    if isinstance(value, bool) or not isinstance(value, int):
        raise StreamError(f"{what} must be an integer, got {value!r}")
    return value


def parse_event(d: dict) -> Event:
    """Parse one raw JSON event dict; reject unknown/missing fields."""
    if not isinstance(d, dict):
        raise StreamError(f"event must be an object, got {type(d).__name__}")
    etype = d.get("type")
    t_us = _strict_int(d.get("t_us"), "t_us")

    if etype == "quote":
        if set(d) != {"t_us", "type", "bid", "ask"}:
            raise StreamError(f"quote event fields must be exactly t_us/type/bid/ask, got {sorted(d)}")
        bid = _strict_int(d["bid"], "bid")
        ask = _strict_int(d["ask"], "ask")
        if ask < bid + 1:
            raise StreamError(f"quote at t_us={t_us}: ask must be >= bid + 1, got bid={bid}, ask={ask}")
        return QuoteEvent(t_us, bid, ask)

    if etype == "jump":
        if set(d) != {"t_us", "type", "size"}:
            raise StreamError(f"jump event fields must be exactly t_us/type/size, got {sorted(d)}")
        size = _strict_int(d["size"], "size")
        if size == 0:
            raise StreamError(f"jump at t_us={t_us}: size must be nonzero")
        return JumpEvent(t_us, size)

    if etype == "arrival":
        if set(d) != {"t_us", "type", "trader", "side_intent", "u_accept"}:
            raise StreamError(
                f"arrival event fields must be exactly t_us/type/trader/side_intent/u_accept, got {sorted(d)}"
            )
        trader = d["trader"]
        side, u = d["side_intent"], d["u_accept"]
        if trader == "informed":
            if side is not None or u is not None:
                raise StreamError(
                    f"arrival at t_us={t_us}: informed arrivals must have null side_intent/u_accept (D5)"
                )
        elif trader == "noise":
            if side not in ("buy", "sell"):
                raise StreamError(f"arrival at t_us={t_us}: noise side_intent must be buy/sell, got {side!r}")
            if isinstance(u, bool) or not isinstance(u, (int, float)) or not (0.0 <= float(u) < 1.0):
                raise StreamError(f"arrival at t_us={t_us}: u_accept must be a float in [0, 1), got {u!r}")
            u = float(u)
        else:
            raise StreamError(f"arrival at t_us={t_us}: trader must be informed/noise, got {trader!r}")
        return ArrivalEvent(t_us, trader, side, u)

    raise StreamError(f"unknown event type {etype!r} at t_us={d.get('t_us')!r}")


def validate_stream(events: list, round_us: int, require_opening_quote: bool = True) -> None:
    """Stream-level invariants (DESIGN.md §0 rule 2, §6.2).

    With ``require_opening_quote`` (vector streams), the first event must be
    a quote at t_us = 0 and arrivals must never precede a quote. Harness
    streams (jumps/arrivals only; quotes injected at run time) validate with
    ``require_opening_quote=False``.
    """
    last_t = -1
    quoted = False
    for ev in events:
        if ev.t_us <= last_t:
            raise StreamError(f"timestamps must be strictly increasing: {ev.t_us} after {last_t}")
        if not (0 <= ev.t_us < round_us):
            raise StreamError(f"t_us={ev.t_us} outside [0, {round_us})")
        last_t = ev.t_us
        if isinstance(ev, QuoteEvent):
            quoted = True
        elif isinstance(ev, ArrivalEvent) and require_opening_quote and not quoted:
            raise StreamError(f"arrival at t_us={ev.t_us} before any quote")
    if require_opening_quote and events:
        first = events[0]
        if not (isinstance(first, QuoteEvent) and first.t_us == 0):
            raise StreamError("first stream event must be a quote at t_us = 0")
    if require_opening_quote and not events:
        raise StreamError("vector stream must contain at least the opening quote")


def parse_stream(raw: list, round_us: int, require_opening_quote: bool = True) -> list:
    if not isinstance(raw, list):
        raise StreamError("event_stream must be an array")
    events = [parse_event(d) for d in raw]
    validate_stream(events, round_us, require_opening_quote=require_opening_quote)
    return events


def event_to_json(ev: Event) -> dict:
    if isinstance(ev, QuoteEvent):
        return {"t_us": ev.t_us, "type": "quote", "bid": ev.bid, "ask": ev.ask}
    if isinstance(ev, JumpEvent):
        return {"t_us": ev.t_us, "type": "jump", "size": ev.size}
    if isinstance(ev, ArrivalEvent):
        return {
            "t_us": ev.t_us,
            "type": "arrival",
            "trader": ev.trader,
            "side_intent": ev.side_intent,
            "u_accept": ev.u_accept,
        }
    raise TypeError(f"not an event: {ev!r}")
