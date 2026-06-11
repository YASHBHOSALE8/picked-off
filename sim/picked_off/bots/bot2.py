"""Bot 2 — Bot 1 plus inventory skew (DESIGN.md §4.4). STRETCH; cuttable.

Responsibilities:
- Take Bot 1's regret-free quotes and shift both by -round(gamma * inv)
  ticks (gamma default 0.5 ticks/unit), re-clamped to ask >= bid + 1.
- Exists to measure the expected-PnL-vs-inventory-variance trade-off
  against Bot 1 on common random numbers (writeup material).

Cut without ceremony if the timebox bites.
"""
