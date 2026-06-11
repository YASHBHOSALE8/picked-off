"""Playability-gate experiment runner (DESIGN.md §5).

Responsibilities:
- Paired bot evaluation with common random numbers: feed the identical
  exogenous stream to Bot 0 and Bot 1 and score both, over N >= 30 seeds.
- The gate predicate: mean PnL(Bot 0) > 0 AND
  mean PnL(Bot 1) >= 1.3 * mean PnL(Bot 0).
- Parameter grid search over (lambda_j, p_jump, lambda_a, alpha, delta0,
  k0) to find passing regimes; reporting (bootstrap CI of the paired mean
  difference, per-component decomposition means) for the gate notebook.
- Emitting the chosen regime as the final level table for DESIGN.md §1.5.

UI work (build step ④) is locked behind this module reporting a pass.
"""
