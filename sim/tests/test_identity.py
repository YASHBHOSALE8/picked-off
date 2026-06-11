"""Tests for the exact accounting identity (DESIGN.md §2.2).

Will assert, over many seeded random streams and quote schedules:
- SC + AS + IC == 2 * PnL in half-ticks, exact integer equality,
  no tolerance — including degenerate rounds (no fills, no jumps).
- The two inventory-cost formulas (per-fill sum vs jump-exposure sum)
  agree exactly.
- Spread captured is always >= 0; every informed fill's adverse-selection
  term is strictly negative.

Implementation lands in build step ②.
"""
