"""Event types and stream parsing/validation (DESIGN.md §6.2, §0).

Responsibilities:
- Dataclasses for the three stream event types: quote, jump, arrival.
- Parsing an event_stream from golden-vector JSON into typed events.
- Stream validation, failing loudly on: non-strictly-increasing t_us,
  timestamps outside [0, round_us), crossed/invalid quotes (ask < bid + 1),
  zero jump sizes, arrivals before any quote is set, and side_intent /
  u_accept fields that are inconsistent with the trader type (non-null
  iff noise).

Pure data layer: no simulation logic, no randomness.
"""
