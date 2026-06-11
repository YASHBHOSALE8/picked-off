"""The normative event loop (DESIGN.md §3).

Responsibilities:
- Consume (params, event_stream) and produce the round result: fills,
  declines (replay channel), jump log, terminal V / cash / inventory.
- Implement arrival resolution exactly as specified: informed traders
  trade iff the quote is strictly through V (ties decline); noise traders
  accept iff u_accept < f(h) = exp(-h/delta0) with h the half-spread.
- Maintain the two output channels: the censored public feed (fills and
  quotes only — what live play and bots may see) and the full log
  (declines, trader types, V path — unlocked for replay).
- All price/time arithmetic in integer ticks/µs. No RNG anywhere.

The deterministic heart of the project: both the golden vectors and the
web engine's TypeScript port conform to this module's behavior.
"""
