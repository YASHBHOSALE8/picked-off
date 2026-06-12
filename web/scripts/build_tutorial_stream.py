"""Build the scripted tutorial stream (final session, onboarding layer).

Hand-choreographed 30-second round: six always-accepting noise arrivals,
one hidden +12 jump at 15.5 s, exactly ONE informed arrival 1.7 s later
(the scripted pick-off — fills unless the player's ask already cleared the
jump), and a small -3 jump near the end. Certified with the same checks
the frozen generator applies to pool streams: §6.3-5 timestamp hygiene,
strictly positive V path, strict monotonicity. sim/ is invoked, not
modified.

Run from the repo root:
    /opt/anaconda3/bin/python3 web/scripts/build_tutorial_stream.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sim"))

from picked_off.events import ArrivalEvent, JumpEvent, event_to_json, validate_stream  # noqa: E402
from picked_off.params import TICK_GRID_US, SimParams  # noqa: E402

OUT = ROOT / "web" / "public" / "streams" / "tutorial.json"

# 30-second practice round at the final regime's delta0; alpha label 0.05
# (one informed arrival among seven).
PARAMS = SimParams(round_us=30_000_000, alpha=0.05)

# u_accept = 0.01 accepts at any sane spread (f(h) = exp(-h/8): a 70-tick
# spread still accepts) — the choreography survives player quote choices.
EVENTS = [
    ArrivalEvent(2_400_007, "noise", "sell", 0.01),
    ArrivalEvent(5_200_011, "noise", "buy", 0.01),
    ArrivalEvent(9_100_013, "noise", "buy", 0.01),
    ArrivalEvent(12_300_017, "noise", "sell", 0.01),
    JumpEvent(15_500_021, 12),  # the hidden move
    ArrivalEvent(17_200_023, "informed", None, None),  # the scripted pick-off
    ArrivalEvent(21_000_029, "noise", "buy", 0.01),
    JumpEvent(24_000_031, -3),
    ArrivalEvent(26_500_037, "noise", "sell", 0.01),
]


def certify_pool_style(params: SimParams, events: list) -> None:
    """Same checks generate_stream applies to pool streams (§6.3-5 + Q5)."""
    validate_stream(events, params.round_us, require_opening_quote=False)
    prev_t = None
    v = params.v0
    for ev in events:
        t = ev.t_us
        if t <= 1 or t % TICK_GRID_US in (0, 1):
            raise SystemExit(f"hygiene violation at t_us={t}")
        if prev_t is not None and t - prev_t < 2:
            raise SystemExit(f"hygiene gap violation at t_us={t}")
        prev_t = t
        if isinstance(ev, JumpEvent):
            v += ev.size
            if v <= 0:
                raise SystemExit(f"V path hit {v} at t_us={t}")


def main() -> None:
    certify_pool_style(PARAMS, EVENTS)
    doc = {
        "stream_id": "tutorial",
        "level": 0,
        "seed": 0,  # hand-authored; provenance only
        "params": PARAMS.to_meta(),
        "event_stream": [event_to_json(ev) for ev in EVENTS],
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    print(f"tutorial stream certified + written: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
