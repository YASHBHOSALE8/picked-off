"""PnL decomposition, markouts, and the exact accounting identity (DESIGN.md §2).

All decomposition arithmetic is in integer half-ticks. Two identities are
asserted with exact integer equality, no tolerance, on every scored round:

  1. total == SC + AS + IC == 2 * (cash_T + inv_T * V_T)        (§2.2)
  2. IC ==  2 * sum over jumps of J_k * inv(t_k-)               (§2.2, jump form)

V(t) lookups use the càdlàg convention: V(s) includes a jump at exactly s.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .engine import RoundResult
from .params import MARKOUT_HORIZONS_US


class ScoringError(AssertionError):
    """An accounting identity failed — a bug by definition."""


@dataclass(frozen=True)
class FillScore:
    t_us: int
    q: int
    sc_half: int  # q * (m - p)        in half-ticks  == ask - bid
    as_half: int  # q * (V_fill - m)   in half-ticks
    ic_half: int  # q * (V_T - V_fill) in half-ticks
    markout_1s: int  # q * (V(min(t+1s, T)) - p), ticks (§2.4)
    markout_5s: int


@dataclass(frozen=True)
class Decomposition:
    total: int  # half-ticks
    spread_captured: int
    adverse_selection: int
    inventory_cost: int

    def to_json(self) -> dict:
        return {
            "total": self.total,
            "spread_captured": self.spread_captured,
            "adverse_selection": self.adverse_selection,
            "inventory_cost": self.inventory_cost,
        }


def value_at(v0: int, jumps: list, t_us: int) -> int:
    """V(t) on the càdlàg convention: jumps with t_k <= t_us are included."""
    times = [j.t_us for j in jumps]
    n = bisect_right(times, t_us)
    return v0 + sum(j.size for j in jumps[:n])


def score_round(result: RoundResult) -> tuple[Decomposition, list[FillScore]]:
    p = result.params
    v_t = result.v_terminal
    fill_scores: list[FillScore] = []
    sc = as_ = ic = 0

    for f in result.fills:
        q = f.q
        sc_i = f.ask - f.bid  # q*(m-p) ticks == (a-b)/2 ticks == a-b half-ticks
        as_i = q * (2 * f.v_at_fill - f.ask - f.bid)
        ic_i = 2 * q * (v_t - f.v_at_fill)
        mo = [
            q * (value_at(p.v0, result.jumps, min(f.t_us + tau, p.round_us)) - f.price)
            for tau in MARKOUT_HORIZONS_US
        ]
        fill_scores.append(FillScore(f.t_us, q, sc_i, as_i, ic_i, mo[0], mo[1]))
        sc += sc_i
        as_ += as_i
        ic += ic_i

    total = sc + as_ + ic

    # Identity 1 (§2.2): telescoping — exact integer equality, no tolerance.
    pnl_half = 2 * (result.cash + result.inventory * v_t)
    if total != pnl_half:
        raise ScoringError(
            f"identity violated: SC+AS+IC = {total} half-ticks but 2*PnL = {pnl_half}"
        )

    # Identity 2 (§2.2): IC == sum over jumps of J_k * inv just before the jump.
    ic_jump_form = 0
    fill_idx = 0
    inv = 0
    fills = result.fills
    for j in result.jumps:
        while fill_idx < len(fills) and fills[fill_idx].t_us < j.t_us:
            inv += fills[fill_idx].q
            fill_idx += 1
        ic_jump_form += j.size * inv
    if ic != 2 * ic_jump_form:
        raise ScoringError(
            f"IC jump-form mismatch: per-fill {ic} half-ticks vs jump-form {2 * ic_jump_form}"
        )

    return Decomposition(total, sc, as_, ic), fill_scores
