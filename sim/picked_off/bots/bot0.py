"""Bot 0 — fixed symmetric spread around the rolling tape mid
(DESIGN.md §4.2).

Responsibilities:
- mid_est = last fill price (V0 before any fill).
- Quote bid = mid_est - k0, ask = mid_est + k0 with fixed integer
  half-spread k0 (default 3 ticks; gate-tunable).
- Re-quote after every fill and on every tick.

The naive baseline the playability gate measures Bot 1 against: it chases
prints and never widens, so it is designed to be picked off in informed
regimes.
"""
