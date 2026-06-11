"""Seeded event-stream generation — the ONLY randomness in the project
(DESIGN.md §6.1, §6.3).

Responsibilities:
- Generate exogenous streams from a seed: Poisson(lambda_j) jump times with
  discrete-Laplace sizes (sign * Geometric(p_jump)), Poisson(lambda_a)
  arrival times, i.i.d. trader types (informed w.p. alpha), noise side
  intents (fair coin), and noise acceptance uniforms u_accept.
- Emit integer-µs timestamps and guarantee strict monotonicity across all
  event types (re-draw on collision), plus the DESIGN.md §6.3 rule 5
  timestamp hygiene: no jump/arrival at t <= 1 µs, on the 100_000 µs
  bot-tick grid or 1 µs after it, or within 1 µs of another exogenous
  event — reserving the quote-injection slots of §4.1.
- Vector certification: simulate the candidate vector against its scripted
  quote schedule and verify |u_accept - f(h)| > 1e-9 at every noise
  arrival, so a 1-ulp exp() difference between Python and JS can never
  flip an outcome; re-roll the seed if any margin fails.
- Write certified golden vectors (meta, event_stream, expected_output
  produced by engine.py + scoring.py) to ../../vectors/.

Engines never import this module's RNG; they are pure functions of streams.
"""
