"""Golden-vector I/O, schema validation, and conformance checking
(DESIGN.md §6.2).

Responsibilities:
- Load and save vector JSON files ({meta, event_stream, expected_output}),
  schema_version 1.
- Validate every schema constraint from DESIGN.md §6.2 / vectors/SCHEMA.md.
- Conformance check: run a vector's stream through engine.py + scoring.py
  and compare against expected_output with exact integer equality on every
  integer field (used by tests/test_vectors.py and, in spirit, by the web
  engine's vitest suite).

No simulation logic of its own and no randomness.
"""
