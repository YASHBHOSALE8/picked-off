"""Generator guarantees (DESIGN.md §6.3): timestamp hygiene on generated
streams, deterministic seeding, the 1e-9 u_accept certification margin, and
the Q5 V>0 parameter guard.
"""

import pytest

from picked_off.engine import noise_accept_prob
from picked_off.events import ArrivalEvent, JumpEvent, QuoteEvent
from picked_off.generator import (
    CertificationError,
    certify,
    check_params_v_positive,
    generate_stream,
)
from picked_off.params import TICK_GRID_US, SimParams


def _exogenous(events):
    return [ev for ev in events if isinstance(ev, (JumpEvent, ArrivalEvent))]


@pytest.mark.parametrize("seed", range(30))
def test_hygiene_on_generated_streams(seed):
    params = SimParams()
    schedule = [(0, 9997, 10003), (30_000_007, 9995, 10005)]
    events = generate_stream(params, seed, schedule)
    quote_times = {ev.t_us for ev in events if isinstance(ev, QuoteEvent)}
    exo = _exogenous(events)
    times = [ev.t_us for ev in exo]
    assert times == sorted(times)
    for t in times:
        assert t > 1, f"hygiene (a) violated: t={t}"
        assert t % TICK_GRID_US not in (0, 1), f"hygiene (b) violated: t={t}"
        assert t not in quote_times, f"exogenous event ties a scripted quote: t={t}"
    for a, b in zip(times, times[1:]):
        assert b - a >= 2, f"hygiene (c) violated: gap {b - a} at t={a}"


def test_streams_are_deterministic_per_seed():
    params = SimParams()
    schedule = [(0, 9997, 10003)]
    assert generate_stream(params, 7, schedule) == generate_stream(params, 7, schedule)
    assert generate_stream(params, 7, schedule) != generate_stream(params, 8, schedule)


def _margin_stream(offset: float):
    params = SimParams()
    f = noise_accept_prob(9997, 10003, params.delta0)
    events = [
        QuoteEvent(0, 9997, 10003),
        ArrivalEvent(500_003, "noise", "buy", f + offset),
    ]
    return params, events


@pytest.mark.parametrize("offset", [5e-10, -5e-10, 0.0])
def test_certification_rejects_margin_violations(offset):
    params, events = _margin_stream(offset)
    with pytest.raises(CertificationError, match="margin"):
        certify(params, events)


@pytest.mark.parametrize("offset", [1e-3, -1e-3, 2e-9, -2e-9])
def test_certification_accepts_clear_margins(offset):
    params, events = _margin_stream(offset)
    certify(params, events)


def test_certify_rejects_hygiene_violations():
    params = SimParams()
    for bad_t in (1, TICK_GRID_US, TICK_GRID_US + 1):
        events = [QuoteEvent(0, 9997, 10003), ArrivalEvent(bad_t, "informed", None, None)]
        with pytest.raises(CertificationError, match="hygiene"):
            certify(params, events)


def test_q5_param_guard_rejects_plausible_negative_v():
    # v0=100 vs round drift RMS sqrt(2*60*1.9/0.01) ~ 151 ticks: clearly unsafe.
    with pytest.raises(CertificationError, match="Q5"):
        check_params_v_positive(SimParams(v0=100, lambda_j=2.0, p_jump=0.1))
    check_params_v_positive(SimParams())  # defaults are safe
