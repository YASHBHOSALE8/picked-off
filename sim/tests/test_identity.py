"""The exact accounting identity (DESIGN.md §2.2) on randomized streams.

Asserts, over 120 seeded random (params, quote-schedule, stream) triples:
- SC + AS + IC == total == 2 * (cash_T + inv_T * V_T) in half-ticks, exact
  integer equality (score_round raises ScoringError otherwise; re-checked
  here explicitly);
- the two inventory-cost formulas agree (also enforced inside score_round);
- spread captured is always >= 0 and equals the sum of posted spreads;
- every informed fill's adverse-selection term is strictly negative;
- degenerate rounds (no arrivals / no jumps / no fills) hold the identity.
"""

import random

import pytest

from picked_off.engine import run_stream
from picked_off.events import QuoteEvent
from picked_off.generator import SEED_RETRY_STEP, CertificationError, generate_stream
from picked_off.params import SimParams
from picked_off.scoring import score_round


def _random_params(rng: random.Random) -> SimParams:
    return SimParams(
        lambda_j=rng.uniform(0.05, 1.5),
        p_jump=rng.uniform(0.08, 0.6),
        lambda_a=rng.choice([0.0, rng.uniform(0.3, 8.0)]),
        alpha=rng.uniform(0.0, 1.0),
        delta0=rng.uniform(0.5, 8.0),
    )


def _random_schedule(rng: random.Random, params: SimParams) -> list:
    """Random-walk quotes: re-quote every 0.5-5 s with a drifting mid."""
    mid = params.v0
    t = 0
    schedule = []
    while t < params.round_us:
        mid += rng.randint(-8, 8)
        k_b, k_a = rng.randint(1, 6), rng.randint(1, 6)
        schedule.append((t, mid - k_b, mid + k_a))
        t += rng.randint(500_000, 5_000_000) + rng.randint(0, 99)  # off round numbers
    return schedule


def _run_seed(seed: int):
    rng = random.Random(seed)
    params = _random_params(rng)
    schedule = _random_schedule(rng, params)
    s = seed
    for _ in range(20):  # re-roll on the rare V<=0 path rejection
        try:
            events = generate_stream(params, s, schedule)
            break
        except CertificationError:
            s += SEED_RETRY_STEP
    else:
        pytest.skip("no V>0 stream found (astronomically unlikely)")
    result = run_stream(params, events)
    decomp, fill_scores = score_round(result)  # raises on any identity violation
    return params, result, decomp, fill_scores


@pytest.mark.parametrize("seed", range(120))
def test_identity_randomized(seed):
    params, result, decomp, fill_scores = _run_seed(seed)

    # Identity, re-checked explicitly (exact integers, no tolerance).
    pnl_half = 2 * (result.cash + result.inventory * result.v_terminal)
    assert decomp.total == pnl_half
    assert (
        decomp.spread_captured + decomp.adverse_selection + decomp.inventory_cost
        == decomp.total
    )

    # SC is the sum of posted spreads at the fills, always >= 0 (§2.3).
    assert decomp.spread_captured == sum(f.ask - f.bid for f in result.fills)
    assert decomp.spread_captured >= 0
    assert all(s.sc_half >= 1 for s in fill_scores)  # min spread 1 tick

    # Every informed fill is strictly picked off at the fill (§2.3).
    for f, s in zip(result.fills, fill_scores):
        if f.trader == "informed":
            assert s.as_half < 0, (f, s)


def test_empty_round():
    params = SimParams(lambda_j=0.0, lambda_a=0.0)
    events = [QuoteEvent(0, params.v0 - 3, params.v0 + 3)]
    result = run_stream(params, events)
    decomp, fill_scores = score_round(result)
    assert (result.cash, result.inventory, result.v_terminal) == (0, 0, params.v0)
    assert decomp.total == decomp.spread_captured == 0
    assert decomp.adverse_selection == decomp.inventory_cost == 0
    assert fill_scores == []


def test_negative_inventory_round_holds_identity():
    """At least one randomized high-alpha round ends short, and it scored cleanly."""
    found = False
    for seed in range(60):
        rng = random.Random(10_000 + seed)
        params = SimParams(alpha=0.8, lambda_j=rng.uniform(0.3, 1.0))
        schedule = [(0, params.v0 - 3, params.v0 + 3)]
        try:
            events = generate_stream(params, 10_000 + seed, schedule)
        except CertificationError:
            continue
        result = run_stream(params, events)
        score_round(result)  # identity asserted inside
        if result.inventory < 0:
            found = True
            break
    assert found, "no negative-inventory round in 60 seeds — suspicious"
