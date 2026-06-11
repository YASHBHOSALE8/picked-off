"""Simulation parameters and the level table (DESIGN.md §1.5).

Responsibilities:
- A frozen dataclass holding one complete parameter set: v0, round_us,
  lambda_j, p_jump, lambda_a, alpha, delta0 (plus bot parameters such as
  Bot 0's half-spread k0 where experiments need them).
- The default values from the DESIGN.md §1.5 table.
- The per-level alpha escalation table (provisional until the playability
  gate in gate.py selects the final regime).
- Round-tripping the parameter block to/from golden-vector `meta.params`.

This is the single home for defaults: no other module hard-codes a
parameter value.
"""
