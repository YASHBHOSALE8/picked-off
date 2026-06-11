"""Bot 1 — Bayesian Glosten-Milgrom dealer (DESIGN.md §4.3).

Responsibilities:
- Grid posterior pi(v) over integer ticks [V0 - W, V0 + W] (W = 200),
  initialized to a point mass at V0.
- Time update: Poisson-mixture convolution with the discrete-Laplace jump
  kernel, truncated at Poisson tail 1e-12.
- Observation updates: own-fill likelihoods
  (buy: alpha*1[v > a] + (1-alpha)*f(h)/2; sell symmetric) and the
  censored quiet-interval factor exp(-lambda_a * dt * p_trade(v)) — the
  reason silence moves the posterior toward "V is inside my quotes".
  The quiet survival factor applies over EVERY elapsed sub-interval,
  including the one immediately preceding a fill (DESIGN.md §4.3 order
  of operations: time update, quiet factor, then fill factor).
- Quoting: the deterministic regret-free fixed point
  ask = ceil(E[V | next arrival buys]), bid = floor(E[V | next arrival
  sells]), iterated with the cycle rule from DESIGN.md §4.3.

numpy only.
"""
