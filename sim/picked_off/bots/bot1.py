"""Bot 1 — Bayesian Glosten-Milgrom dealer (DESIGN.md §4.3).

Grid posterior pi(v) over integer ticks [V0-W, V0+W] (W=200), point mass
at V0 (V0 is public). Updates, in the §4.3 order at every callback:

  1. time update for the elapsed delta: Poisson-mixture convolution with
     the discrete-Laplace jump kernel, K = smallest integer with
     P(Poisson(mu) <= K) >= 1 - 1e-12;
  2. censored quiet survival factor exp(-lambda_a * delta * p_trade(v))
     for the SAME delta — applied on every elapsed sub-interval, including
     the one immediately preceding a fill (the pre-fill survival factor);
  3. on fills only: the fill likelihood
     buy:  L(v) = alpha*1[v > a] + (1-alpha)*f(h)/2
     sell: L(v) = alpha*1[v < b] + (1-alpha)*f(h)/2.

Quoting: the GM regret-free fixed point (ask = ceil E[V | next arrival
buys], bid = floor E[V | next arrival sells]) iterated with the §4.3
cycle guard (on a revisited pair, stop with the widest pair seen in the
cycle); if 500 iterations elapse with neither fixed point nor cycle, the
last iterate is used (documented fallback; the cap exceeds the worst
observed widen-to-grid-edge/snap-back cycle period by ~5x at W=200).

Numerical notes (documented approximations, §4.3): posterior mass that
convolves past the grid edge is truncated and renormalized; jump-kernel
tails below 1e-15 cumulative mass are trimmed; the 1 µs injection slip
(quotes apply at decision time + 1 µs) is ignored in the elapsed-delta
bookkeeping. numpy only.
"""

from __future__ import annotations

import math

import numpy as np

from ..engine import noise_accept_prob
from ..params import BOT1_GRID_W, SimParams

_POISSON_TAIL = 1e-12
_KERNEL_TRIM = 1e-15
_FP_MAX_ITERS = 500  # §4.3 iteration budget (v1.1: raised from 50)


class Bot1:
    def __init__(self, grid_w: int = BOT1_GRID_W):
        self.grid_w = grid_w

    # -- lifecycle ---------------------------------------------------------

    def on_start(self, params: SimParams) -> tuple[int, int]:
        self.p = params
        self.values = np.arange(params.v0 - self.grid_w, params.v0 + self.grid_w + 1)
        self.pi = np.zeros(self.values.size)
        self.pi[self.grid_w] = 1.0  # point mass at public V0 (§1.1/D6)
        self.last_t = 0
        self._d_powers = [np.array([1.0])]  # D^{*0} = identity; lazily extended
        self._base_kernel = self._laplace_kernel(params.p_jump)
        self._kernel_cache: dict[int, np.ndarray] = {}
        self.bid, self.ask = self._regret_free()
        return self.bid, self.ask

    def on_fill(self, t_us: int, side: str, price: int) -> tuple[int, int]:
        self._advance(t_us)
        self._fill_update(side)
        self.bid, self.ask = self._regret_free()
        return self.bid, self.ask

    def on_tick(self, t_us: int) -> tuple[int, int]:
        self._advance(t_us)
        self.bid, self.ask = self._regret_free()
        return self.bid, self.ask

    # -- posterior updates (§4.3 order: time, quiet survival, fill) --------

    def _advance(self, t_us: int) -> None:
        delta_us = t_us - self.last_t
        if delta_us > 0:
            self._time_update(delta_us)
            self._quiet_update(delta_us)
        self.last_t = t_us

    @staticmethod
    def _laplace_kernel(p_jump: float) -> np.ndarray:
        """Discrete-Laplace jump pmf D(j) = 0.5*p*(1-p)^(|j|-1), j != 0 (§1.1),
        truncated where the per-side geometric tail drops below _KERNEL_TRIM."""
        if p_jump >= 1.0:  # every jump is exactly +/-1 tick
            return np.array([0.5, 0.0, 0.5])
        j_max = max(1, math.ceil(math.log(_KERNEL_TRIM) / math.log(1.0 - p_jump)))
        offs = np.arange(-j_max, j_max + 1)
        pmf = np.where(offs == 0, 0.0, 0.5 * p_jump * (1.0 - p_jump) ** (np.abs(offs) - 1))
        return pmf / pmf.sum()

    def _transition_kernel(self, delta_us: int) -> np.ndarray:
        """Sum_k Poisson(k; mu) D^{*k}, K per the 1e-12 tail rule (§4.3)."""
        kern = self._kernel_cache.get(delta_us)
        if kern is not None:
            return kern
        mu = self.p.lambda_j * delta_us / 1e6
        # K = smallest integer with CDF >= 1 - 1e-12 (incremental pmf).
        term = math.exp(-mu)
        cdf = term
        k_needed = 0
        while cdf < 1.0 - _POISSON_TAIL:
            k_needed += 1
            term *= mu / k_needed
            cdf += term
        while len(self._d_powers) <= k_needed:
            self._d_powers.append(np.convolve(self._d_powers[-1], self._base_kernel))
        width = self._d_powers[k_needed].size
        kern = np.zeros(width)
        w = math.exp(-mu)
        for k in range(k_needed + 1):
            dk = self._d_powers[k]
            pad = (width - dk.size) // 2
            kern[pad : pad + dk.size] += w * dk
            w *= mu / (k + 1)
        kern /= kern.sum()
        self._kernel_cache[delta_us] = kern
        return kern

    def _time_update(self, delta_us: int) -> None:
        kern = self._transition_kernel(delta_us)
        full = np.convolve(self.pi, kern)
        c = (kern.size - 1) // 2  # kernel's zero-offset index
        self.pi = full[c : c + self.pi.size]  # grid-edge mass truncated (§4.3)
        self._renorm()

    def _quiet_update(self, delta_us: int) -> None:
        f = noise_accept_prob(self.bid, self.ask, self.p.delta0)
        outside = (self.values < self.bid) | (self.values > self.ask)
        p_trade = self.p.alpha * outside + (1.0 - self.p.alpha) * f
        self.pi = self.pi * np.exp(-self.p.lambda_a * (delta_us / 1e6) * p_trade)
        self._renorm()

    def _fill_update(self, side: str) -> None:
        f = noise_accept_prob(self.bid, self.ask, self.p.delta0)
        informed = (self.values > self.ask) if side == "buy" else (self.values < self.bid)
        like = self.p.alpha * informed + (1.0 - self.p.alpha) * 0.5 * f
        self.pi = self.pi * like
        if self.pi.sum() <= 0.0:
            # Observation impossible under the truncated posterior (only
            # reachable at alpha=1 with all mass on the wrong side): restart
            # from the least-wrong hypothesis set.
            self.pi = informed.astype(float)
            if self.pi.sum() == 0.0:
                self.pi = np.ones_like(self.pi)
        self._renorm()

    def _renorm(self) -> None:
        self.pi /= self.pi.sum()

    # -- GM regret-free quoting (§4.3) --------------------------------------

    def _cond_expectations(self, bid: int, ask: int) -> tuple[float, float]:
        f = noise_accept_prob(bid, ask, self.p.delta0)
        alpha = self.p.alpha
        noise_w = (1.0 - alpha) * 0.5 * f
        mean_all = float(self.values @ self.pi)

        above = self.values > ask
        mass_above = float(self.pi[above].sum())
        ev_above = float((self.values[above] * self.pi[above]).sum())
        den_buy = alpha * mass_above + noise_w
        e_buy = (alpha * ev_above + noise_w * mean_all) / den_buy if den_buy > 0 else math.inf

        below = self.values < bid
        mass_below = float(self.pi[below].sum())
        ev_below = float((self.values[below] * self.pi[below]).sum())
        den_sell = alpha * mass_below + noise_w
        e_sell = (alpha * ev_below + noise_w * mean_all) / den_sell if den_sell > 0 else -math.inf

        return e_buy, e_sell

    def _regret_free(self) -> tuple[int, int]:
        mean = float(self.values @ self.pi)
        ask = math.ceil(mean) + 1
        bid = math.floor(mean) - 1
        hi = int(self.values[-1]) + 1
        lo = int(self.values[0]) - 1
        # §4.3 pseudocode: the freshly computed pair is checked against the
        # seen-set inside the same iteration, so a revisit produced by the
        # final compute of the budget is still caught by the cycle rule.
        seen: dict[tuple[int, int], int] = {(ask, bid): 0}
        history: list[tuple[int, int]] = [(ask, bid)]
        for _ in range(_FP_MAX_ITERS):
            e_buy, e_sell = self._cond_expectations(bid, ask)
            new_ask = max(min(math.ceil(e_buy), hi) if math.isfinite(e_buy) else hi, bid + 1)
            new_bid = min(max(math.floor(e_sell), lo) if math.isfinite(e_sell) else lo, new_ask - 1)
            if (new_ask, new_bid) == (ask, bid):
                break  # fixed point
            if (new_ask, new_bid) in seen:
                cycle = history[seen[(new_ask, new_bid)] :]
                ask = max(p[0] for p in cycle)  # widest pair in the cycle (§4.3)
                bid = min(p[1] for p in cycle)
                break
            ask, bid = new_ask, new_bid
            seen[(ask, bid)] = len(history)
            history.append((ask, bid))
        if ask < bid + 1:
            ask = bid + 1
        return int(bid), int(ask)
