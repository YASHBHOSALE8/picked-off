"""Engine fail-loudly validation (DESIGN.md §6.3-4): malformed events must
raise EngineError, never be silently misrouted or coerced.
"""

import pytest

from picked_off.engine import Engine, EngineError, run_stream
from picked_off.events import ArrivalEvent, JumpEvent, QuoteEvent
from picked_off.params import SimParams

P = SimParams()
Q = QuoteEvent(0, 9997, 10003)


def _arrival_round(arrival):
    return run_stream(P, [Q, arrival])


@pytest.mark.parametrize(
    "arrival",
    [
        ArrivalEvent(500_003, "Informed", None, None),  # bad trader case
        ArrivalEvent(500_003, "informd", "buy", 0.0),  # typo'd trader
        ArrivalEvent(500_003, "maker", None, None),
        ArrivalEvent(500_003, "noise", "hold", 0.0),  # bad side
        ArrivalEvent(500_003, "noise", "BUY", 0.0),
        ArrivalEvent(500_003, "noise", None, 0.5),  # noise needs a side
        ArrivalEvent(500_003, "noise", "buy", 1.5),  # u out of range
        ArrivalEvent(500_003, "noise", "buy", -0.1),
        ArrivalEvent(500_003, "noise", "buy", None),
        ArrivalEvent(500_003, "noise", "buy", True),  # bool is not a prob
        ArrivalEvent(500_003, "informed", "buy", None),  # informed must be null
        ArrivalEvent(500_003, "informed", None, 0.3),
    ],
)
def test_malformed_arrivals_raise(arrival):
    with pytest.raises(EngineError):
        _arrival_round(arrival)


@pytest.mark.parametrize(
    "events",
    [
        [QuoteEvent(0, 9996.5, 10003.5)],  # float prices
        [QuoteEvent(0, 9997, True)],  # bool price
        [Q, JumpEvent(500_003, 2.0)],  # float jump
        [Q, JumpEvent(500_003, True)],
        [Q, JumpEvent(500_003.0, 2)],  # float timestamp
    ],
)
def test_non_integer_fields_raise(events):
    with pytest.raises(EngineError):
        run_stream(P, events)


def test_valid_events_still_pass():
    result = run_stream(
        P,
        [Q, JumpEvent(500_003, 7), ArrivalEvent(700_007, "informed", None, None)],
    )
    assert len(result.fills) == 1  # V=10007 > ask 10003 -> informed buy
    assert result.fills[0].price == 10003


def test_engine_rejects_out_of_order_and_unquoted():
    eng = Engine(P)
    eng.apply(Q)
    eng.apply(JumpEvent(500_003, 1))
    with pytest.raises(EngineError, match="strictly increasing"):
        eng.apply(JumpEvent(500_003, 1))
    with pytest.raises(EngineError, match="no quote"):
        run_stream(P, [ArrivalEvent(500_003, "informed", None, None)])
