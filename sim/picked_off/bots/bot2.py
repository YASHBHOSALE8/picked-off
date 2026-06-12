"""Bot 2 — Bot 1 plus inventory skew (DESIGN.md §4.4). STRETCH; cuttable.

Bot 1's regret-free quotes, both shifted by -round(gamma * inv) ticks
(gamma default 0.5 ticks/unit), re-clamped to ask >= bid + 1 (the shift
preserves the spread, so clamping never actually binds). round() is
round-half-AWAY-FROM-ZERO (§4.4, pinned in v1.1): at gamma = 0.5 every
odd inventory is a .5 tie, and Python's banker's rounding would zero the
skew at |inv| = 1. Long inventory shades both quotes down to attract
buyers and repel sellers — trading expected PnL for inventory variance
against Bot 1 on common random numbers (writeup material).
"""

from __future__ import annotations

import math

from ..params import SimParams
from .bot1 import Bot1


def _round_half_away(x: float) -> int:
    """round-half-away-from-zero (the §4.4 tie rule; NOT Python's banker's)."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


class Bot2(Bot1):
    def __init__(self, gamma: float = 0.5, grid_w: int | None = None):
        super().__init__(**({"grid_w": grid_w} if grid_w is not None else {}))
        self.gamma = gamma
        self.inv = 0

    def _skewed(self, quotes: tuple[int, int]) -> tuple[int, int]:
        bid, ask = quotes
        shift = -_round_half_away(self.gamma * self.inv)
        bid, ask = bid + shift, ask + shift
        if ask < bid + 1:  # defensive; shift preserves the spread
            ask = bid + 1
        # The skewed quotes are what actually stands in the market, so the
        # posterior's quiet/fill likelihoods must condition on them.
        self.bid, self.ask = bid, ask
        return bid, ask

    def on_start(self, params: SimParams) -> tuple[int, int]:
        self.inv = 0
        return self._skewed(super().on_start(params))

    def on_fill(self, t_us: int, side: str, price: int) -> tuple[int, int]:
        self.inv += -1 if side == "buy" else +1  # customer buy -> dealer sells
        return self._skewed(super().on_fill(t_us, side, price))

    def on_tick(self, t_us: int) -> tuple[int, int]:
        return self._skewed(super().on_tick(t_us))
