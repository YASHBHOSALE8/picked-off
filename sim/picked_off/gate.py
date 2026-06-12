"""Playability-gate experiment runner (DESIGN.md §5).

Paired bot evaluation with common random numbers: the identical exogenous
stream (jumps, arrival times, types, side intents, uniforms) is fed to
Bot 0 and Bot 1 for each seed; outcomes differ only through the quotes.

Gate predicate (§5, incl. the D7 guard):

    mean PnL(Bot 0) > 0   and   mean PnL(Bot 1) >= 1.3 * mean PnL(Bot 0)

Reported alongside (not part of the gate): medians (Q1 — the gate stays
mean-based), bootstrap 95% CI of the paired mean difference, and the
per-component decomposition means for both bots. PnL figures are in ticks
(half-ticks / 2). UI work (build step ④) is locked behind a pass.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .bots.base import run_bot
from .bots.bot0 import Bot0
from .bots.bot1 import Bot1
from .generator import SEED_RETRY_STEP, CertificationError, generate_stream
from .params import SimParams
from .scoring import score_round

GATE_RATIO = 1.3
GATE_MIN_SEEDS = 30
_BASE_SEED = 20_000


@dataclass(frozen=True)
class BotStats:
    mean: float  # ticks
    median: float
    spread_captured: float  # per-component decomposition means, ticks
    adverse_selection: float
    inventory_cost: float


@dataclass(frozen=True)
class GateResult:
    params: SimParams
    k0: int
    n: int
    bot0: BotStats
    bot1: BotStats
    diff_mean: float  # mean paired difference (bot1 - bot0), ticks
    ci_lo: float  # bootstrap 95% CI of the paired mean difference
    ci_hi: float
    passes: bool

    def to_row(self) -> dict:
        p = self.params
        return {
            "lambda_j": p.lambda_j, "p_jump": p.p_jump, "lambda_a": p.lambda_a,
            "alpha": p.alpha, "delta0": p.delta0, "k0": self.k0, "n": self.n,
            "mean0": self.bot0.mean, "mean1": self.bot1.mean,
            "median0": self.bot0.median, "median1": self.bot1.median,
            "sc0": self.bot0.spread_captured, "as0": self.bot0.adverse_selection,
            "ic0": self.bot0.inventory_cost,
            "sc1": self.bot1.spread_captured, "as1": self.bot1.adverse_selection,
            "ic1": self.bot1.inventory_cost,
            "diff_mean": self.diff_mean, "ci_lo": self.ci_lo, "ci_hi": self.ci_hi,
            "passes": self.passes,
        }


def _stream_for_seed(params: SimParams, seed: int) -> list:
    s = seed
    for _ in range(100):
        try:
            return generate_stream(params, s, None)
        except CertificationError:  # V<=0 path (Q5): deterministic re-roll
            s += SEED_RETRY_STEP
    raise CertificationError(f"no V>0 stream near seed {seed}")


def _score_ticks(params: SimParams, events: list, bot) -> tuple[float, float, float, float]:
    decomp, _ = score_round(run_bot(params, events, bot))
    return (
        decomp.total / 2.0,
        decomp.spread_captured / 2.0,
        decomp.adverse_selection / 2.0,
        decomp.inventory_cost / 2.0,
    )


def bootstrap_ci(diffs: np.ndarray, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap 95% CI of the mean paired difference."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diffs.size, size=(n_boot, diffs.size))
    means = diffs[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def gate_passes(mean0: float, mean1: float, n: int) -> bool:
    """The §5 predicate, incl. the D7 guard and the N >= 30 requirement."""
    return n >= GATE_MIN_SEEDS and mean0 > 0 and mean1 >= GATE_RATIO * mean0


def evaluate(
    params: SimParams,
    k0: int,
    n_seeds: int = GATE_MIN_SEEDS,
    base_seed: int = _BASE_SEED,
    bot0_factory=Bot0,
    bot1_factory=Bot1,
) -> GateResult:
    """Paired evaluation of one parameter set over n_seeds common streams."""
    from .generator import check_params_v_positive

    check_params_v_positive(params)  # Q5: clean rejection before any streams
    rows0, rows1 = [], []
    for i in range(n_seeds):
        events = _stream_for_seed(params, base_seed + i * 7_919)
        rows0.append(_score_ticks(params, events, bot0_factory(k0)))
        rows1.append(_score_ticks(params, events, bot1_factory()))
    a0, a1 = np.array(rows0), np.array(rows1)

    def stats(a: np.ndarray) -> BotStats:
        return BotStats(
            mean=float(a[:, 0].mean()),
            median=float(np.median(a[:, 0])),
            spread_captured=float(a[:, 1].mean()),
            adverse_selection=float(a[:, 2].mean()),
            inventory_cost=float(a[:, 3].mean()),
        )

    s0, s1 = stats(a0), stats(a1)
    diffs = a1[:, 0] - a0[:, 0]
    ci_lo, ci_hi = bootstrap_ci(diffs)
    passes = gate_passes(s0.mean, s1.mean, n_seeds)
    return GateResult(
        params=params, k0=k0, n=n_seeds, bot0=s0, bot1=s1,
        diff_mean=float(diffs.mean()), ci_lo=ci_lo, ci_hi=ci_hi, passes=passes,
    )


def grid_search(combos: list[tuple[SimParams, int]], n_seeds: int = GATE_MIN_SEEDS,
                progress=None, on_skip=None) -> list[GateResult]:
    """Evaluate every (params, k0) combo; combos sharing params share streams
    (common random numbers across the whole grid row). Parameter corners
    rejected by the Q5 guard are skipped (on_skip callback), not fatal."""
    results = []
    for i, (params, k0) in enumerate(combos):
        try:
            r = evaluate(params, k0, n_seeds=n_seeds)
        except CertificationError as e:
            if on_skip is not None:
                on_skip(i + 1, len(combos), params, k0, str(e))
            continue
        results.append(r)
        if progress is not None:
            progress(i + 1, len(combos), r)
    return results
