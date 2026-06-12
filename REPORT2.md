# REPORT2 — Build steps ② (sim + vectors) and ③ (bots + playability gate)

Date: 2026-06-12. Scope: everything Python; no web work (step ④ is now unlocked by the gate).

## Summary

- **Simulator** (`sim/picked_off/`): events, engine, scoring, generator, vectors — implemented exactly per DESIGN.md §§0–3, 6. Integer ticks/µs throughout; both §2.2 identity assertions (telescoping and jump-form IC) hold with exact integer equality on every scored round.
- **12 frozen golden vectors** in `vectors/`, including the §6.2 smoke vector byte-identical to the spec and a hand-verified vector with the full arithmetic written out.
- **236 tests, all green** (`cd sim && python -m pytest`), 0.4 s.
- **Bots**: harness (D11 +1 µs injection), Bot 0, Bot 1 (grid posterior, censored-quiet + ordered fill updates, GM fixed-point quoting), and Bot 2 (stretch — implemented, not cut).
- **Playability gate: PASSED.** 8 of 72 grid regimes satisfy §5; the level table is finalized at `lambda_j = 0.2, p_jump = 0.2, lambda_a = 4.0, delta0 = 8.0, k0 = 2` and written back to DESIGN.md §1.5 (changelog §10). UI work (step ④) is unblocked.
- The implementation was adversarially reviewed against the spec mid-session (multi-agent); 23 findings were filed and triaged, leading to one behavioral fix in Bot 1 (iteration budget), one in Bot 2 (rounding), engine/validator hardening, 41 new tests, and a grid re-run. Details below.

## Test summary

| File | Tests | Covers |
| --- | --- | --- |
| test_identity.py | 122 | §2.2 identities exact on 120 randomized (params, quote-schedule, stream) triples; empty rounds; negative inventory; SC ≥ 0; informed AS < 0 per fill |
| test_vectors.py | 40 | schema validity, exact conformance, AND full §6.3 certification (hygiene + 1e-9 margin) for all 12 frozen vectors; hand-verified arithmetic asserted field by field |
| test_generator.py | 44 | §6.3-5 hygiene (all three clauses, generation + certify sides), per-seed determinism, u_accept margin rejection/acceptance both sides, per-event field certification, Q5 guard |
| test_engine.py | 19 | fail-loudly validation: malformed traders/sides/u_accept, non-integer prices/jumps/timestamps, ordering, quote-before-arrival |
| test_bots.py | 16 | D11 injection legality incl. hand-built collision cases, harness rejects malformed/hygiene-violating streams and non-integer quotes, CRN reproducibility, Bot 0 semantics, Bot 1 posterior health/learning/comparative statics, p_jump=1 corner, Bot 2 tie rounding |
| test_gate.py | 4 | §5 predicate boundaries (1.3× exact, D7 guard, N ≥ 30), paired-stream CRN, bootstrap CI sanity, Q5 corner skipping |
| **Total** | **236** | |

## Golden vector inventory (vectors/)

All 12 validate, conform exactly, and pass full certification. Frozen under the v1.0 parameters they embed (vectors are self-contained).

1. `smoke_two_arrivals` — the DESIGN.md §6.2 example, **byte-identical** to the spec block.
2. `hand_verified_mixed` — informed decline → informed pick-off → quote move → noise fill → noise balk; SC=16, AS=−14, IC=0, total=2 half-ticks, verified by hand (arithmetic in `test_vectors.py` docstring and below).
3. `empty_round` — no arrivals/jumps; identity at all-zeros.
4. `noise_only` — alpha=0.
5. `informed_only` — alpha=1, fills and declines.
6. `jump_heavy` — lambda_j=3.0.
7. `declines_only` — wide quotes; every arrival declines (the censoring showcase).
8. `quote_changes_mid_round` — 9-step scripted quote schedule.
9. `markout_clamp` — fill inside the last second; both markouts clamp at T.
10. `negative_inventory` — round ends ≤ −3 units.
11. `long_round_trip` — inventory swings ≥ 2, ends flat.
12. `kitchen_sink` — busy schedule at v1.0 defaults: 20+ fills, 10+ declines, 10+ jumps.

Hand verification (vector 2, half-ticks): informed buy at 10005 with V=10009: sc=10, as=−18, ic=+8; noise sell at 10004 with V=10009: sc=6, as=+4, ic=−8. SC=16, AS=−14, IC=0; cash=1 tick, inv=0, V_T=10005 → total = 2 = 2·PnL. ✓

## Gate results

Grid: `lambda_j ∈ {0.2, 0.5} × delta0 ∈ {4, 8} × alpha ∈ {0.05, 0.1, 0.2, 0.3, 0.4, 0.5} × k0 ∈ {2, 3, 5}`, `lambda_a = 4.0`, `p_jump = 0.2` fixed; 30 paired seeds per combo, common random numbers; PnL in ticks. Full table: `notebooks/gate_results.csv` (produced by `notebooks/gate_results.py`).

**8 / 72 regimes pass** (not trivially-at-all-alpha, so Q2's EWMA Bot 0 variant was not triggered):

| lambda_j | delta0 | alpha | k0 | Bot 0 | Bot 1 | ratio | diff 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2 | 4.0 | 0.2 | 2 | 37.8 | 52.3 | 1.38× | [−12.0, 41.3] |
| 0.2 | 4.0 | 0.3 | 2 | 27.5 | 63.5 | 2.31× | [6.7, 67.7] |
| 0.2 | 4.0 | 0.4 | 2 | 4.2 | 32.3 | 7.70× | [7.3, 48.5] |
| **0.2** | **8.0** | **0.3** | **2** | **69.4** | **93.7** | **1.35×** | **[−7.5, 53.2]** |
| **0.2** | **8.0** | **0.4** | **2** | **35.1** | **61.1** | **1.74×** | **[0.3, 50.0]** |
| **0.2** | **8.0** | **0.5** | **2** | **18.2** | **55.6** | **3.05×** | **[13.6, 63.1]** |
| 0.5 | 8.0 | 0.1 | 2 | 68.3 | 94.7 | 1.39× | [−17.8, 72.5] |
| 0.5 | 8.0 | 0.2 | 3 | 14.3 | 47.5 | 3.31× | [−16.2, 85.7] |

(Bold = the chosen level family.) Full 72-row grid:

<details>
<summary>All 72 regimes (click to expand)</summary>

| lambda_j | delta0 | alpha | k0 | Bot 0 mean | Bot 1 mean | med 0 | med 1 | diff CI | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2 | 4.0 | 0.05 | 2 | 191.2 | 173.3 | 157.5 | 196.5 | [-81.7, 37.4] | fail |
| 0.2 | 4.0 | 0.05 | 3 | 219.8 | 173.3 | 186.0 | 196.5 | [-133.7, 35.9] | fail |
| 0.2 | 4.0 | 0.05 | 5 | 225.1 | 173.3 | 194.5 | 196.5 | [-150.6, 40.5] | fail |
| 0.2 | 4.0 | 0.1 | 2 | 82.0 | 75.3 | 139.0 | 161.0 | [-50.2, 29.4] | fail |
| 0.2 | 4.0 | 0.1 | 3 | 133.1 | 75.3 | 169.5 | 161.0 | [-115.2, -11.1] | fail |
| 0.2 | 4.0 | 0.1 | 5 | 162.4 | 75.3 | 175.5 | 161.0 | [-160.1, -25.3] | fail |
| 0.2 | 4.0 | 0.2 | 2 | 37.8 | 52.3 | 123.5 | 143.5 | [-12.0, 41.3] | PASS |
| 0.2 | 4.0 | 0.2 | 3 | 101.4 | 52.3 | 150.5 | 143.5 | [-90.1, -12.6] | fail |
| 0.2 | 4.0 | 0.2 | 5 | 141.2 | 52.3 | 163.0 | 143.5 | [-145.8, -39.7] | fail |
| 0.2 | 4.0 | 0.3 | 2 | 27.5 | 63.5 | 117.0 | 146.5 | [6.7, 67.7] | PASS |
| 0.2 | 4.0 | 0.3 | 3 | 86.4 | 63.5 | 136.5 | 146.5 | [-62.5, 12.5] | fail |
| 0.2 | 4.0 | 0.3 | 5 | 124.0 | 63.5 | 142.5 | 146.5 | [-113.1, -17.1] | fail |
| 0.2 | 4.0 | 0.4 | 2 | 4.2 | 32.3 | 90.0 | 98.5 | [7.3, 48.5] | PASS |
| 0.2 | 4.0 | 0.4 | 3 | 66.3 | 32.3 | 115.5 | 98.5 | [-59.5, -10.6] | fail |
| 0.2 | 4.0 | 0.4 | 5 | 103.5 | 32.3 | 128.5 | 98.5 | [-111.5, -34.7] | fail |
| 0.2 | 4.0 | 0.5 | 2 | -8.0 | 23.5 | 79.0 | 93.5 | [6.0, 59.0] | fail |
| 0.2 | 4.0 | 0.5 | 3 | 51.0 | 23.5 | 103.0 | 93.5 | [-56.3, -0.8] | fail |
| 0.2 | 4.0 | 0.5 | 5 | 86.8 | 23.5 | 111.5 | 93.5 | [-105.4, -25.6] | fail |
| 0.2 | 8.0 | 0.05 | 2 | 307.6 | 185.5 | 213.5 | 182.5 | [-227.8, -39.3] | fail |
| 0.2 | 8.0 | 0.05 | 3 | 375.1 | 185.5 | 280.5 | 182.5 | [-275.7, -113.1] | fail |
| 0.2 | 8.0 | 0.05 | 5 | 451.3 | 185.5 | 366.5 | 182.5 | [-360.4, -175.4] | fail |
| 0.2 | 8.0 | 0.1 | 2 | 144.8 | 114.5 | 184.0 | 196.5 | [-75.4, 8.3] | fail |
| 0.2 | 8.0 | 0.1 | 3 | 232.2 | 114.5 | 247.0 | 196.5 | [-179.2, -63.4] | fail |
| 0.2 | 8.0 | 0.1 | 5 | 332.4 | 114.5 | 343.0 | 196.5 | [-295.1, -149.2] | fail |
| 0.2 | 8.0 | 0.2 | 2 | 85.9 | 86.8 | 166.5 | 190.5 | [-32.6, 29.7] | fail |
| 0.2 | 8.0 | 0.2 | 3 | 182.0 | 86.8 | 226.0 | 190.5 | [-142.9, -55.4] | fail |
| 0.2 | 8.0 | 0.2 | 5 | 282.9 | 86.8 | 309.0 | 190.5 | [-259.4, -143.1] | fail |
| 0.2 | 8.0 | 0.3 | 2 | 69.4 | 93.7 | 152.5 | 179.0 | [-7.5, 53.2] | PASS |
| 0.2 | 8.0 | 0.3 | 3 | 157.8 | 93.7 | 209.0 | 179.0 | [-110.0, -27.3] | fail |
| 0.2 | 8.0 | 0.3 | 5 | 250.6 | 93.7 | 273.0 | 179.0 | [-219.3, -106.4] | fail |
| 0.2 | 8.0 | 0.4 | 2 | 35.1 | 61.1 | 114.0 | 139.0 | [0.3, 50.0] | PASS |
| 0.2 | 8.0 | 0.4 | 3 | 122.1 | 61.1 | 176.5 | 139.0 | [-94.7, -32.7] | fail |
| 0.2 | 8.0 | 0.4 | 5 | 213.5 | 61.1 | 241.0 | 139.0 | [-197.4, -114.2] | fail |
| 0.2 | 8.0 | 0.5 | 2 | 18.2 | 55.6 | 106.0 | 125.5 | [13.6, 63.1] | PASS |
| 0.2 | 8.0 | 0.5 | 3 | 98.4 | 55.6 | 152.5 | 125.5 | [-76.2, -11.9] | fail |
| 0.2 | 8.0 | 0.5 | 5 | 182.6 | 55.6 | 203.5 | 125.5 | [-173.8, -85.2] | fail |
| 0.5 | 4.0 | 0.05 | 2 | 112.4 | 124.6 | 125.0 | 126.5 | [-44.9, 70.4] | fail |
| 0.5 | 4.0 | 0.05 | 3 | 133.9 | 124.6 | 195.5 | 126.5 | [-81.6, 74.7] | fail |
| 0.5 | 4.0 | 0.05 | 5 | 166.7 | 124.6 | 174.0 | 126.5 | [-117.4, 56.7] | fail |
| 0.5 | 4.0 | 0.1 | 2 | -60.3 | -4.4 | 72.0 | 111.0 | [6.5, 109.8] | fail |
| 0.5 | 4.0 | 0.1 | 3 | 8.0 | -4.4 | 124.5 | 111.0 | [-56.9, 31.4] | fail |
| 0.5 | 4.0 | 0.1 | 5 | 82.4 | -4.4 | 140.0 | 111.0 | [-160.6, -25.6] | fail |
| 0.5 | 4.0 | 0.2 | 2 | -174.1 | 9.0 | 1.5 | 71.0 | [51.1, 348.4] | fail |
| 0.5 | 4.0 | 0.2 | 3 | -54.1 | 9.0 | 69.5 | 71.0 | [-30.7, 181.1] | fail |
| 0.5 | 4.0 | 0.2 | 5 | 51.0 | 9.0 | 113.5 | 71.0 | [-112.8, 44.3] | fail |
| 0.5 | 4.0 | 0.3 | 2 | -201.2 | 19.2 | -9.5 | 56.0 | [61.3, 412.5] | fail |
| 0.5 | 4.0 | 0.3 | 3 | -68.7 | 19.2 | 57.0 | 56.0 | [-24.9, 221.5] | fail |
| 0.5 | 4.0 | 0.3 | 5 | 36.3 | 19.2 | 110.5 | 56.0 | [-87.7, 63.3] | fail |
| 0.5 | 4.0 | 0.4 | 2 | -234.9 | -10.0 | -28.0 | 30.0 | [57.6, 429.8] | fail |
| 0.5 | 4.0 | 0.4 | 3 | -91.4 | -10.0 | 30.5 | 30.0 | [-27.9, 216.0] | fail |
| 0.5 | 4.0 | 0.4 | 5 | 13.2 | -10.0 | 79.5 | 30.0 | [-88.2, 54.6] | fail |
| 0.5 | 4.0 | 0.5 | 2 | -248.6 | 5.9 | -36.0 | 24.5 | [73.3, 480.9] | fail |
| 0.5 | 4.0 | 0.5 | 3 | -103.7 | 5.9 | 23.5 | 24.5 | [-9.8, 261.5] | fail |
| 0.5 | 4.0 | 0.5 | 5 | -4.8 | 5.9 | 66.5 | 24.5 | [-60.9, 101.8] | fail |
| 0.5 | 8.0 | 0.05 | 2 | 273.3 | 195.3 | 190.0 | 202.0 | [-143.4, -16.6] | fail |
| 0.5 | 8.0 | 0.05 | 3 | 341.7 | 195.3 | 252.0 | 202.0 | [-254.3, -37.6] | fail |
| 0.5 | 8.0 | 0.05 | 5 | 418.6 | 195.3 | 363.5 | 202.0 | [-324.6, -121.3] | fail |
| 0.5 | 8.0 | 0.1 | 2 | 68.3 | 94.7 | 139.5 | 148.5 | [-17.8, 72.5] | PASS |
| 0.5 | 8.0 | 0.1 | 3 | 127.4 | 94.7 | 202.5 | 148.5 | [-98.5, 41.1] | fail |
| 0.5 | 8.0 | 0.1 | 5 | 243.1 | 94.7 | 316.0 | 148.5 | [-223.8, -70.2] | fail |
| 0.5 | 8.0 | 0.2 | 2 | -127.4 | 47.5 | 60.5 | 190.5 | [117.6, 238.0] | fail |
| 0.5 | 8.0 | 0.2 | 3 | 14.3 | 47.5 | 138.5 | 190.5 | [-16.2, 85.7] | PASS |
| 0.5 | 8.0 | 0.2 | 5 | 178.7 | 47.5 | 260.0 | 190.5 | [-209.9, -68.4] | fail |
| 0.5 | 8.0 | 0.3 | 2 | -159.6 | 39.0 | 22.0 | 156.5 | [131.9, 277.3] | fail |
| 0.5 | 8.0 | 0.3 | 3 | -0.1 | 39.0 | 121.0 | 156.5 | [3.6, 75.5] | fail |
| 0.5 | 8.0 | 0.3 | 5 | 159.0 | 39.0 | 227.5 | 156.5 | [-179.5, -68.6] | fail |
| 0.5 | 8.0 | 0.4 | 2 | -206.0 | 19.7 | -1.0 | 153.0 | [146.0, 322.5] | fail |
| 0.5 | 8.0 | 0.4 | 3 | -40.0 | 19.7 | 88.5 | 153.0 | [34.9, 89.7] | fail |
| 0.5 | 8.0 | 0.4 | 5 | 118.8 | 19.7 | 184.0 | 153.0 | [-144.7, -59.6] | fail |
| 0.5 | 8.0 | 0.5 | 2 | -225.4 | 2.6 | -18.0 | 148.0 | [141.2, 339.6] | fail |
| 0.5 | 8.0 | 0.5 | 3 | -60.4 | 2.6 | 73.5 | 148.0 | [28.3, 108.5] | fail |
| 0.5 | 8.0 | 0.5 | 5 | 90.2 | 2.6 | 162.5 | 148.0 | [-134.5, -43.9] | fail |

</details>

## Chosen level parameters (written to DESIGN.md §1.5)

`lambda_j = 0.2, p_jump = 0.2, lambda_a = 4.0, delta0 = 8.0`, Bot-0 reference `k0 = 2`; levels escalate alpha 0.10 → 0.50. Chosen because the naive baseline stays viable (positive mean) at *every* level while the value of information escalates monotonically — a clean difficulty ramp:

| Level | alpha | Bot 0 mean | Bot 1 mean | ratio | Bot 0 median | Bot 1 median | gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.10 | 144.8 | 114.5 | 0.79× | 184.0 | 196.5 | fail |
| 2 | 0.20 | 85.9 | 86.8 | 1.01× | 166.5 | 190.5 | fail |
| 3 | 0.30 | 69.4 | 93.7 | 1.35× | 152.5 | 179.0 | **PASS** |
| 4 | 0.40 | 35.1 | 61.1 | 1.74× | 114.0 | 139.0 | **PASS** |
| 5 | 0.50 | 18.2 | 55.6 | 3.05× | 106.0 | 125.5 | **PASS** |

§5 requires *a* passing regime to exist — satisfied three times over within the ladder itself. Q1 (medians): reported above; medians agree with the means at L3–L5 (Bot 1 ahead), so the mean-based gate is not carried by lucky tails. The gate stays mean-based per the locked spec.

## Bot 1 vs Bot 0 decomposition at the chosen regime (mean ticks/round, 30 paired seeds)

| Level (alpha) | SC₀ | AS₀ | IC₀ | | SC₁ | AS₁ | IC₁ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 (0.10) | 375.9 | −215.7 | −15.4 | | 308.9 | −178.5 | −15.9 |
| 2 (0.20) | 367.1 | −269.5 | −11.7 | | 359.6 | −259.3 | −13.5 |
| 3 (0.30) | 338.6 | −287.2 | 17.9 | | 348.5 | −274.4 | 19.6 |
| 4 (0.40) | 302.9 | −268.9 | 1.2 | | 314.8 | −241.3 | −12.4 |
| 5 (0.50) | 268.7 | −262.8 | 12.3 | | 286.0 | −225.0 | −5.4 |

(Abridged from gate_results.csv.) The mechanism is exactly the Glosten–Milgrom story: at low alpha Bot 1's tight regret-free quotes simply give up spread revenue relative to a fixed ±2 (SC 309 vs 376) without enough adverse selection to punish the naive bot. As alpha rises, Bot 1 both **loses less to adverse selection** (reading fills *and silences*) and **captures more spread** (it widens intelligently when uncertain), while inventory cost stays mean-≈0 for both, as theory predicts for exogenous jumps. Writeup material.

## DESIGN.md amendments (explicit diffs; full text in §10 changelog)

1. **§1.5** — level table: `lambda_j 0.5 → 0.2`, `delta0 4.0 → 8.0`, `k0` row added (`= 2`), "provisional; gate-tuned" → "final; gate passes at L3–L5"; difficulty-ramp paragraph added. §1.3 default `delta0 4.0 → 8.0`; §4.2 `k0 default 3 → reference 2`.
2. **§4.3** — `repeat up to 50 times` → `repeat up to 500 times`, plus documentation of the widen/snap-back limit cycle (period ~50–60 at W=200) and the last-iterate fallback. Reason: the 50-cap silently fell through on up to ~30% of quoting calls in dispersed regimes, roughly halving Bot 1 PnL there (measured 92 → 183 ticks/3 rounds at lj=0.5, d0=4, a=0.5).
3. **§4.3** — grid-width note updated for the final regime (W=200 is >8σ).
4. **§4.4** — `round` pinned to round-half-away-from-zero (banker's rounding zeroes the skew at |inv|=1 with gamma=0.5) and Bot 2's posterior conditions on the *skewed* standing quotes.
5. **§6.2** — "duplicated verbatim in vectors/SCHEMA.md" → "mirrored (in abridged form)"; **vectors/SCHEMA.md** determinism rule 3 corrected (meta.params rates/probabilities are JSON floats — the old text would have made a literal TS validator reject every frozen vector).
6. **§9 Q5** — marked resolved (param-level 6σ guard + realized-path rejection + grid skips rejected corners).

## Adversarial review outcome (mid-session)

A 4-lens spec-conformance review (engine/scoring, generator/vectors, Bot-1 math, harness/gate/tests) filed 23 findings. The automated verification pass was cut short by a session limit after confirming 1 (the SCHEMA.md rule-3 error); I triaged the other 22 manually, reproducing each before acting. Outcomes: 2 behavioral fixes (Bot 1 iteration budget — confirmed by experiment, grid re-run; Bot 2 rounding), 1 boundary fix (cycle detection covers the final iterate), 1 corner fix (Bot 1 at p_jump=1.0), ~10 fail-loudly/validation hardenings (engine arrival/type checks, harness stream+quote validation, certify field round-trip, meta.params and schema_version strictness, fills/declines array checks, gate N≥30 in the pass predicate, Q5 grid skip, ceil-division tick schedule), and 41 new tests covering the flagged gaps. The grid re-run after the Bot 1 fix left all 8 passing regimes and the level choice unchanged (the fix mainly affected `delta0=4`/`lambda_j=0.5` corners that fail anyway).

## Unresolved / flagged (not hidden)

1. **L3's paired-difference CI includes zero** ([−7.5, 53.2]). The §5 gate is on means and is formally passed (and L4/L5 are CI-positive), but at L3 the 30-seed evidence for Bot 1's edge is suggestive, not significant. If stronger evidence is wanted, raise n_seeds — the runner takes ~4 s per combo at n=30.
2. **Bot 1 loses to Bot 0 at low alpha by design**: regret-free quotes are zero-expected-edge (the GM theorem), so in noise-dominated regimes a wide fixed spread out-earns it. This is the intended lesson (levels 1–2 reward simple spread-printing) but the writeup should present it explicitly rather than as "Bot 1 is better, full stop."
3. **`lambda_a` and `p_jump` were not swept** in the grid (fixed at 4.0 / 0.2). The gate passed without them; sweeping them remains open for the writeup's robustness section.
4. **The §4.3 10 Hz quiet-factor discretization** (quotes/V treated constant per slice) remains the spec'd approximation, as documented; the writeup must state it.
5. **Verification workflow incompleteness**: 22/23 review findings were human-triaged rather than machine-adversarially verified (session limit). All were reproduced or assessed before fixing, but a re-run of the verify pass would restore the two-independent-judgments bar the project has used so far.
6. Bot 2 exists and is tested but did not run in the gate (per spec it is Bot 1's stretch comparison, not a gate participant); the Bot1-vs-Bot2 inventory-variance comparison is open writeup material for step ⑤.

## Reproduction

```bash
cd sim && /opt/anaconda3/bin/python3 -m pytest          # 236 tests
/opt/anaconda3/bin/python3 notebooks/gate_results.py    # regenerates gate_results.csv (~5 min)
```
