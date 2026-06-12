"""Bot 0 — fixed symmetric spread around the rolling tape mid (DESIGN.md §4.2).

mid_est = last fill price (V0 before any fill); quotes mid_est ± k0. The
naive baseline the playability gate measures Bot 1 against: it chases
prints and never widens, so it is designed to be picked off in informed
regimes.
"""

from __future__ import annotations

from ..params import DEFAULT_K0, SimParams


class Bot0:
    def __init__(self, k0: int = DEFAULT_K0):
        if not (isinstance(k0, int) and k0 >= 1):
            raise ValueError(f"k0 must be an int >= 1, got {k0!r}")
        self.k0 = k0
        self.mid_est = 0

    def _quotes(self) -> tuple[int, int]:
        return self.mid_est - self.k0, self.mid_est + self.k0

    def on_start(self, params: SimParams) -> tuple[int, int]:
        self.mid_est = params.v0
        return self._quotes()

    def on_fill(self, t_us: int, side: str, price: int) -> tuple[int, int]:
        self.mid_est = price
        return self._quotes()

    def on_tick(self, t_us: int) -> tuple[int, int]:
        return self._quotes()
