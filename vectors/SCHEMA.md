# Golden test vector schema (v1)

This file duplicates DESIGN.md §6 for convenience next to the vectors.
**On any conflict, DESIGN.md wins.**

A vector is one JSON file: `{meta, event_stream, expected_output}`. Both
engines (Python sim, TypeScript web) must reproduce `expected_output` from
`(meta.params, event_stream)` with **exact integer equality** on every
integer field. Engines never draw randomness; the Python generator is the
only RNG in the project.

Units: prices/V in integer ticks (1 tick = $0.01), timestamps in integer
microseconds from round start, PnL decomposition in integer half-ticks
(1 half-tick = $0.005).

## Top level

| Field | Type | Meaning |
| --- | --- | --- |
| `meta.schema_version` | int | This schema is version **1**. |
| `meta.name` | string | Unique vector name. |
| `meta.description` | string | What the vector exercises. |
| `meta.seed` | int | Generator seed (provenance only; engines must not use it). |
| `meta.params` | object | `v0` (ticks), `round_us` (µs), `lambda_j` (jumps/s), `p_jump`, `lambda_a` (arrivals/s), `alpha`, `delta0` (ticks). |
| `event_stream` | array | Ordered events, **strictly increasing `t_us`** across all types, `0 ≤ t_us < round_us`. |
| `expected_output` | object | See below. |

## Event types

| Event | Fields | Constraints |
| --- | --- | --- |
| quote | `{"t_us", "type": "quote", "bid": int, "ask": int}` | ticks; `ask ≥ bid + 1`; the first stream event must be a quote at `t_us = 0` |
| jump | `{"t_us", "type": "jump", "size": int}` | ticks; `size ≠ 0` |
| arrival | `{"t_us", "type": "arrival", "trader": "informed"\|"noise", "side_intent": "buy"\|"sell"\|null, "u_accept": float\|null}` | `side_intent` and `u_accept` are non-null **iff** `trader == "noise"` (an informed trader's side is endogenous: derived from V vs quotes) |

Arrival resolution (DESIGN.md §1.3/§3): informed buys at the ask iff
`ask < V` (strict), sells at the bid iff `bid > V` (strict), else declines;
noise trades its `side_intent` iff `u_accept < exp(-h/delta0)` with
`h = (ask - bid)/2`, else declines. `"buy"`/`"sell"` are always the
**customer's** side.

## expected_output

| Field | Type | Meaning |
| --- | --- | --- |
| `fills` | array | Every fill, in order: `{"t_us", "side": "buy"\|"sell", "price": int, "v_at_fill": int, "trader", "markout_1s": int, "markout_5s": int}`. Markouts: `q · (V(min(t+tau, T)) − price)` in ticks, q = −1 for `"buy"`, +1 for `"sell"`, clamped at round end. |
| `declines` | array | Every decline (the replay reveal): `{"t_us", "trader", "side_intent": "buy"\|"sell"\|null, "reason": "v_inside_quotes"\|"balked_at_spread"}`. |
| `v_terminal` | int | V after all events, ticks. |
| `inventory_terminal` | int | Units, signed. |
| `cash_terminal` | int | Ticks. |
| `pnl_decomposition_half_ticks` | object | `{"total", "spread_captured", "adverse_selection", "inventory_cost"}`, integers in half-ticks. Must satisfy exactly: `total = spread_captured + adverse_selection + inventory_cost` and `total = 2 × (cash_terminal + inventory_terminal × v_terminal)`. |

## Cross-language determinism

1. Integer fields compare with exact equality; no tolerances.
2. The only float comparison in an engine is `u_accept < exp(-h/delta0)`
   (IEEE-754 double in both languages). The generator certifies every
   vector with margin `|u_accept − f(h)| > 1e−9` at every noise arrival
   against the scripted quotes, so a 1-ulp `exp()` difference can never
   flip an outcome.
3. `u_accept` is written with ≤ 17 significant digits (exact double
   round-trip). All other numbers are JSON integers.
4. Engines must validate streams and fail loudly on malformed vectors.
5. Timestamp hygiene (DESIGN.md §4.1/§6.3 rule 5): certified vectors
   additionally guarantee that no jump or arrival timestamp is ≤ 1 µs,
   lands on a multiple of 100_000 µs or 1 µs after one, or is within
   1 µs of another exogenous event. This reserves the run-time
   quote-injection slots; engines still assert only plain strict
   monotonicity.

## Example

```json
{
  "meta": {
    "schema_version": 1,
    "name": "smoke_two_arrivals",
    "description": "One noise fill at the ask, one informed decline, one jump.",
    "seed": 42,
    "params": { "v0": 10000, "round_us": 60000000, "lambda_j": 0.5, "p_jump": 0.2,
                "lambda_a": 4.0, "alpha": 0.3, "delta0": 4.0 }
  },
  "event_stream": [
    { "t_us": 0,        "type": "quote",   "bid": 9997, "ask": 10003 },
    { "t_us": 400037,   "type": "arrival", "trader": "noise", "side_intent": "buy", "u_accept": 0.41370000 },
    { "t_us": 900211,   "type": "arrival", "trader": "informed", "side_intent": null, "u_accept": null },
    { "t_us": 1500421,  "type": "jump",    "size": -7 }
  ],
  "expected_output": {
    "fills": [
      { "t_us": 400037, "side": "buy", "price": 10003, "v_at_fill": 10000,
        "trader": "noise", "markout_1s": 3, "markout_5s": 10 }
    ],
    "declines": [
      { "t_us": 900211, "trader": "informed", "side_intent": null, "reason": "v_inside_quotes" }
    ],
    "v_terminal": 9993,
    "inventory_terminal": -1,
    "cash_terminal": 10003,
    "pnl_decomposition_half_ticks": {
      "total": 20, "spread_captured": 6, "adverse_selection": 0, "inventory_cost": 14
    }
  }
}
```
