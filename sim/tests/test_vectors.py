"""Golden-vector conformance tests (DESIGN.md §6).

Will assert, for every ../../vectors/*.json:
- The vector validates against the §6.2 schema (strict monotone t_us,
  quote-before-arrival, field constraints).
- Running the event_stream through the engine reproduces expected_output
  with exact integer equality on every integer field (fills, declines,
  terminal state, decomposition, markouts).
- The decomposition block internally satisfies
  total == spread_captured + adverse_selection + inventory_cost.

Implementation lands in build step ②.
"""
