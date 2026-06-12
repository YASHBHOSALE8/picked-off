"""Playability-gate grid search (DESIGN.md §5) — build step ③.

Runs the paired Bot 1 vs Bot 0 grid over (lambda_j, p_jump, lambda_a,
alpha, delta0, k0) with >= 30 common-random-numbers seeds per combo, and
writes notebooks/gate_results.csv (one row per combo, all regimes tried,
pass/fail per the §5 predicate incl. the Bot0>0 guard) plus a console
summary. Medians are reported per Q1 (the gate stays mean-based).

Run from the repo root:
    /opt/anaconda3/bin/python3 notebooks/gate_results.py
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sim"))

from picked_off.gate import grid_search  # noqa: E402
from picked_off.params import SimParams  # noqa: E402

OUT = Path(__file__).resolve().parent / "gate_results.csv"

GRID = [
    (SimParams(lambda_j=lj, lambda_a=la, alpha=a, delta0=d0), k0)
    for lj in (0.2, 0.5)
    for la in (4.0,)
    for d0 in (4.0, 8.0)
    for a in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5)
    for k0 in (2, 3, 5)
]

FIELDS = [
    "lambda_j", "p_jump", "lambda_a", "alpha", "delta0", "k0", "n",
    "mean0", "mean1", "median0", "median1",
    "sc0", "as0", "ic0", "sc1", "as1", "ic1",
    "diff_mean", "ci_lo", "ci_hi", "passes",
]


def main() -> None:
    t0 = time.time()
    rows = []

    def progress(i, total, r):
        rows.append(r.to_row())
        with open(OUT, "w", newline="") as fh:  # rewrite each combo: crash-safe
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        p = r.params
        print(
            f"[{i:3d}/{total}] lj={p.lambda_j} d0={p.delta0} a={p.alpha} k0={r.k0} | "
            f"bot0={r.bot0.mean:8.1f} bot1={r.bot1.mean:8.1f} ticks | "
            f"diff CI [{r.ci_lo:7.1f},{r.ci_hi:7.1f}] | {'PASS' if r.passes else 'fail'}",
            flush=True,
        )

    results = grid_search(GRID, n_seeds=30, progress=progress)
    n_pass = sum(r.passes for r in results)
    print(f"\n{n_pass}/{len(results)} combos pass the gate "
          f"({time.time() - t0:.0f}s). Full table: {OUT}")
    for r in results:
        if r.passes:
            p = r.params
            print(f"  PASS lj={p.lambda_j} d0={p.delta0} a={p.alpha} k0={r.k0}: "
                  f"bot0={r.bot0.mean:.1f} bot1={r.bot1.mean:.1f} "
                  f"(x{r.bot1.mean / r.bot0.mean:.2f})")


if __name__ == "__main__":
    main()
