"""PnL decomposition, markouts, and the exact accounting identity (DESIGN.md §2).

Responsibilities:
- Per-fill terms in integer half-ticks: spread captured q*(m - p),
  adverse selection q*(V_fill - m), inventory cost q*(V_T - V_fill).
- The identity assertion SC + AS + IC == 2 * PnL (half-ticks), exact
  integer equality, no tolerance — asserted on every scored round.
- The equivalent jump-sum form of inventory cost
  (sum over jumps of J_k * inv(t_k-)), asserted equal to the per-fill form.
- Markout diagnostics MO_i(tau) = q_i * (V(min(t_i + tau, T)) - p_i) for
  tau in {1s, 5s}, clamped at round end (diagnostics only; not score).

Consumes engine output; produces the pnl_decomposition_half_ticks block
of golden vectors and the score/replay payloads.
"""
