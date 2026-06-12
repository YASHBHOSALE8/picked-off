"""Playability-gate runner (DESIGN.md §5): predicate boundaries, the D7 and
N >= 30 guards, common-random-numbers pairing, bootstrap CI, and the Q5
parameter-corner skip path.
"""

import numpy as np
import pytest

import picked_off.gate as gate_mod
from picked_off.gate import (
    GATE_MIN_SEEDS,
    bootstrap_ci,
    evaluate,
    gate_passes,
    grid_search,
)
from picked_off.params import SimParams


def test_gate_predicate_boundaries():
    n = GATE_MIN_SEEDS
    assert gate_passes(100.0, 130.0, n)  # exactly 1.3x passes (>= per §5 formula)
    assert not gate_passes(100.0, 129.9, n)
    assert not gate_passes(0.0, 100.0, n)  # D7 guard: bot0 must be > 0
    assert not gate_passes(-5.0, 100.0, n)
    assert not gate_passes(100.0, 130.0, n - 1)  # N >= 30 is part of the gate
    assert gate_passes(0.1, 0.13, n)


def test_bootstrap_ci_degenerate_and_sane():
    lo, hi = bootstrap_ci(np.full(30, 7.0))
    assert lo == hi == 7.0
    rng = np.random.default_rng(0)
    diffs = rng.normal(10.0, 5.0, size=30)
    lo, hi = bootstrap_ci(diffs)
    assert lo < diffs.mean() < hi
    assert hi - lo < 4 * 5.0  # sane width for n=30


class _FixedBot:
    """Quotes a fixed book forever; records the params it saw."""

    def __init__(self, k0=3):
        self.k0 = k0

    def on_start(self, params):
        self.params = params
        return params.v0 - self.k0, params.v0 + self.k0

    def on_fill(self, t_us, side, price):
        return self.params.v0 - self.k0, self.params.v0 + self.k0

    def on_tick(self, t_us):
        return self.params.v0 - self.k0, self.params.v0 + self.k0


def test_evaluate_pairs_streams_and_undersized_n_cannot_pass(monkeypatch):
    params = SimParams()
    calls = []
    real = gate_mod._stream_for_seed

    def counting(p, seed):
        calls.append(seed)
        return real(p, seed)

    monkeypatch.setattr(gate_mod, "_stream_for_seed", counting)
    r = evaluate(params, k0=3, n_seeds=2, bot0_factory=_FixedBot, bot1_factory=_FixedBot)
    # One stream per seed, shared by both bots (common random numbers, §5)...
    assert len(calls) == 2
    # ...identical bots on identical streams => identical stats.
    assert r.bot0 == r.bot1
    assert r.diff_mean == 0.0
    # And an undersized run can never record a pass, whatever the means say.
    assert not r.passes


def test_grid_search_skips_q5_rejected_corners():
    bad = SimParams(v0=100, lambda_j=2.0, p_jump=0.1)  # fails the Q5 sigma rule
    skipped = []
    results = grid_search(
        [(bad, 3)],
        n_seeds=2,
        on_skip=lambda i, total, params, k0, reason: skipped.append(reason),
    )
    assert results == []
    assert len(skipped) == 1 and "Q5" in skipped[0]
