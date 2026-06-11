"""Common bot interface and harness (DESIGN.md §4.1).

Responsibilities:
- The bot protocol: on_start(params) -> (bid, ask),
  on_fill(t_us, side, price) -> (bid, ask), on_tick(t_us) -> (bid, ask).
- The 10 Hz decision clock: on_tick fires at t = k * 100_000 µs for
  k = 1..599 (on_start covers t = 0); quote changes are permitted only at
  on_fill / on_tick callbacks so bot behavior is exactly reproducible.
- The harness that splices bot quote decisions into the engine's event
  loop as quote events stamped decision time + 1 µs (DESIGN.md §4.1
  injection rule; the generator's timestamp hygiene, §6.3 rule 5,
  guarantees the slot is free so strict monotonicity still holds), while
  feeding every bot the identical exogenous stream (common random numbers
  for gate.py).
- Enforcement of the information barrier: bots receive the public feed
  only.
"""
