"""Simulation parameters and the level table (DESIGN.md §1.5).

Single home for defaults: no other module hard-codes a parameter value.
Prices are integer ticks, timestamps integer microseconds (DESIGN.md §0).
"""

from __future__ import annotations

from dataclasses import dataclass

# Bot decision clock period (DESIGN.md §4.1): on_tick fires at k * TICK_GRID_US
# for k = 1 .. (round_us // TICK_GRID_US) - 1; on_start covers t = 0.
TICK_GRID_US = 100_000

# Markout horizons (DESIGN.md §2.4), microseconds.
MARKOUT_HORIZONS_US = (1_000_000, 5_000_000)

# Bot 0 default half-spread in ticks (DESIGN.md §4.2); gate-tunable.
DEFAULT_K0 = 3

# Bot 1 grid half-width in ticks (DESIGN.md §4.3).
BOT1_GRID_W = 200

# Level table (DESIGN.md §1.5): levels escalate alpha, everything else fixed.
# Provisional until gate.py finalizes the regime (DESIGN.md §5).
LEVEL_ALPHAS = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.40, 5: 0.50}


@dataclass(frozen=True)
class SimParams:
    """One complete parameter set; mirrors golden-vector ``meta.params``."""

    v0: int = 10_000
    round_us: int = 60_000_000
    lambda_j: float = 0.5
    p_jump: float = 0.2
    lambda_a: float = 4.0
    alpha: float = 0.3
    delta0: float = 4.0

    def __post_init__(self) -> None:
        if not (isinstance(self.v0, int) and self.v0 > 0):
            raise ValueError(f"v0 must be a positive int, got {self.v0!r}")
        if not (isinstance(self.round_us, int) and self.round_us > 0):
            raise ValueError(f"round_us must be a positive int, got {self.round_us!r}")
        if not (0.0 < self.p_jump <= 1.0):
            raise ValueError(f"p_jump must be in (0, 1], got {self.p_jump!r}")
        if self.lambda_j < 0 or self.lambda_a < 0:
            raise ValueError("lambda_j and lambda_a must be >= 0")
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {self.alpha!r}")
        if self.delta0 <= 0:
            raise ValueError(f"delta0 must be > 0, got {self.delta0!r}")

    def to_meta(self) -> dict:
        """The exact ``meta.params`` object of DESIGN.md §6.2."""
        return {
            "v0": self.v0,
            "round_us": self.round_us,
            "lambda_j": self.lambda_j,
            "p_jump": self.p_jump,
            "lambda_a": self.lambda_a,
            "alpha": self.alpha,
            "delta0": self.delta0,
        }

    @classmethod
    def from_meta(cls, d: dict) -> "SimParams":
        expected = {"v0", "round_us", "lambda_j", "p_jump", "lambda_a", "alpha", "delta0"}
        if set(d) != expected:
            raise ValueError(
                f"meta.params keys must be exactly {sorted(expected)}, got {sorted(d)}"
            )
        return cls(
            v0=d["v0"],
            round_us=d["round_us"],
            lambda_j=float(d["lambda_j"]),
            p_jump=float(d["p_jump"]),
            lambda_a=float(d["lambda_a"]),
            alpha=float(d["alpha"]),
            delta0=float(d["delta0"]),
        )
