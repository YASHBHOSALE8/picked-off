# Picked Off — Design Document

**Version 1.0 — 2026-06-11.**
**This document is the source of truth.** If code and DESIGN.md disagree, DESIGN.md wins until it is explicitly amended. It is written so that a stranger could implement the simulator from this file alone.

Picked Off is a browser-based market-making game and research project built on the Glosten–Milgrom adverse-selection model. The player is the sole dealer in a single-instrument market, posting a bid and an ask against a hidden fair value. Order flow is a mixture of noise traders and informed traders who know the fair value exactly. The score decomposes PnL into three exact components — spread captured, adverse selection, and inventory cost — so the player can see *how* they made or lost money, not just how much. A Python simulator is the canonical engine; a React/TypeScript web game mirrors it bit-for-bit via shared golden test vectors; research bots and a writeup analyze optimal play.

---

## 0. Conventions and glossary

| Term | Meaning |
| --- | --- |
| tick | Price unit. 1 tick = $0.01. All prices are **integers in ticks**. |
| half-tick | PnL decomposition unit. 1 half-tick = $0.005. Used so the decomposition is exact in integer arithmetic (quote mids can fall between ticks). |
| µs | Time unit. All timestamps are **integers in microseconds** from round start. |
| V, V(t) | Hidden fair value at time t, in ticks. Càdlàg pure jump process. |
| dealer | The quoting agent: the human player (web) or a bot (sim). |
| customer | An arriving trader (informed or noise). |
| arrival | A customer reaching the market. May end in a **fill** or a **decline**. |
| fill | An arrival that trades: 1 unit at the dealer's bid or ask. |
| decline | An arrival that walks away without trading. Invisible live; revealed in replay (§1.4). |
| side | Always named from the **customer's** perspective: `"buy"` = customer buys at the dealer's ask (dealer sells); `"sell"` = customer sells at the dealer's bid (dealer buys). |
| q_i | Dealer position change at fill i: q = +1 when the customer sells (dealer buys), q = −1 when the customer buys (dealer sells). |
| tape | The sequence of fills (time, side, price). In this single-dealer market the public tape and the dealer's own fill record are the same stream. |
| markout | Post-fill fair-value move diagnostic (§2.5). Not part of the scoring identity. |

Engine-wide rules:

1. **Integer arithmetic everywhere that scoring is concerned.** Prices, V, jump sizes, cash, and inventory are integers (ticks / units). The decomposition is computed in half-ticks (integers). The accounting identity (§2) must hold **exactly** — no float tolerance.
2. **Time** is integer µs. Round length `T = 60_000_000` µs. All events have `0 ≤ t_us < T`. Event timestamps within a stream are **strictly increasing** across all event types; the generator guarantees this and engines must assert it (so tie-breaking rules are never needed). Dealer quote decisions made at run time (bot harness §4.1, live player §7.3) are stamped at the smallest unoccupied µs **strictly after** their decision time, and the generator keeps exogenous timestamps clear of those injection slots (§6.3 rule 5) — so the invariant survives quote injection in every run mode.
3. **No RNG in engines.** All randomness is pre-drawn by the Python stream generator into the event stream (§6). Both engines are deterministic pure functions `(params, event_stream) → outputs`.
4. The only floating-point quantities in the whole system are the noise-acceptance probability `f(h)` and the pre-drawn uniforms `u_accept`. Both engines use IEEE-754 doubles; the generator enforces a comparison margin so a 1-ulp difference in `exp()` across languages can never flip an outcome (§6.3).

---

## 1. Market model

### 1.1 Hidden fair value V

- Pure jump process: **V is constant between jumps** and jumps at the event times of a Poisson process with rate `lambda_j` (jumps per second). No drift, no diffusion.
- Initial value `V(0) = V0 = 10_000` ticks ($100.00). **V0 is public knowledge** — the player and all bots know the fair value exactly at t = 0. Everything after that is hidden.
- Jump sizes are i.i.d. **discrete Laplace** in ticks: `J = S · G`, where
  - `S` is a uniform random sign, P(S = +1) = P(S = −1) = 1/2,
  - `G ~ Geometric(p_J)` on {1, 2, 3, …}: `P(G = g) = p_J · (1 − p_J)^(g−1)`, mean `1/p_J` ticks.
  - Hence `J` is symmetric, never zero (every jump moves the price), with `E[|J|] = 1/p_J` and `E[J²] = (2 − p_J)/p_J²`.
- V is càdlàg: at a jump time `t_k` with size `J_k`, `V(t_k) = V(t_k⁻) + J_k`. Because timestamps never tie (§0 rule 2), "V at an arrival" is unambiguous: it is V after applying every stream event with a strictly smaller timestamp.
- V is not clamped: it may in principle go to 0 or below. With default parameters this has negligible probability over a 60 s round; the engine does not special-case it.
- Terminal value `V_T` = V after all events in the round (equivalently, V(T⁻)).

### 1.2 Dealer quotes

- The dealer's only controls are a single **bid** `b` and a single **ask** `a`, both integers in ticks, with `a ≥ b + 1` (uncrossed, minimum spread 1 tick). The engine rejects invalid quotes.
- **One unit per fill.** Each fill trades exactly 1 unit. Quotes are persistent: after a fill, the same bid and ask remain standing (no depletion, no re-arm delay). The dealer is always quoting both sides while a quote is set.
- Quote changes take effect immediately at their event timestamp (no latency model — see cut list §7.5).
- Quote mid `m = (a + b)/2` may fall on a half-tick; this is why scoring runs in half-ticks.
- A quote must be set before the first arrival of the stream. Engines must raise an error on an arrival with no quote set (golden vectors always open with a quote event; the live game forces an opening quote before the clock starts).
- No inventory limit: the dealer's position may grow arbitrarily. Inventory risk is priced by the scoring (§2), not by a hard cap.

### 1.3 Order flow

- Customer arrivals follow a Poisson process with rate `lambda_a` (arrivals per second), **independent of the V process**.
- Each arrival is independently **informed** with probability `alpha`, otherwise **noise**.

**Informed trader.** Observes the current fair value `V = V(t)` exactly, plus the dealer's quotes:

- buys 1 unit at the ask **iff `a < V`** (strict),
- sells 1 unit at the bid **iff `b > V`** (strict),
- otherwise (i.e. `b ≤ V ≤ a`) **declines** — walks away without trading.

The two trade conditions are mutually exclusive because `a ≥ b + 1`. Ties decline: an informed trader will not trade at exactly fair value. An informed trader has no exogenous "side intent" — its side is determined by V and the quotes.

**Noise trader.** Does not observe V:

- Side intent is a pre-drawn fair coin: buy or sell with probability 1/2 each.
- Accepts the quote on its side with probability `f(h)` where `h = (a − b)/2` is the **half-spread in ticks** (possibly half-integer):

  `f(h) = exp(−h / delta0)`,  `delta0 > 0` in ticks (default 4.0).

  Acceptance is decided by a pre-drawn uniform `u_accept ∈ [0, 1)`: the noise trader **accepts iff `u_accept < f(h)`**. A buyer fills at the ask; a seller fills at the bid. Otherwise it declines ("balked at the spread").
- Design choice (locked for v1): the distance in `f` is measured from the **dealer's own quote mid**, so both sides sit at distance h and noise acceptance depends only on the posted spread, not on where the quotes sit relative to V or the tape. This keeps noise flow exogenous to V (clean Glosten–Milgrom likelihoods for Bot 1, §4.3) and makes informed flow the *only* punishment for a mispriced mid — which is the lesson the game teaches. The alternative (noise elasticity relative to a tape-derived reference mid) is recorded in §9 as a rejected variant.

Summary of an arrival's outcome probabilities given quotes (b, a) and fair value v:

| outcome | probability |
| --- | --- |
| buy at ask (visible fill) | `alpha · 1[v > a] + (1 − alpha) · ½ · f(h)` |
| sell at bid (visible fill) | `alpha · 1[v < b] + (1 − alpha) · ½ · f(h)` |
| decline (invisible live) | `alpha · 1[b ≤ v ≤ a] + (1 − alpha) · (1 − f(h))` |

These three sum to 1. The indicator conditions use strict integer comparisons (`v > a` means `v ≥ a + 1`).

### 1.4 Censoring (LOCKED DECISION)

**Declined arrivals are invisible during live play and revealed in the post-round replay.**

- **Live:** the dealer sees only fills (time, side, price) and their own quotes. No arrival ticks, no decline notifications, no trader-type labels. Silence is ambiguous.
- **Replay (post-round):** full reveal — every arrival including declines, each labeled with trader type and outcome (informed passed because V was inside the quotes; noise balked at the spread), overlaid on the true V path and the dealer's quote history.

Rationale, in three registers:

1. **Realism.** Real dealers do not observe the customers who looked at the quote and walked away. The information environment of OTC market making is exactly this: you see your fills and the public tape, never the declines.
2. **Math.** Censoring is what makes the Bayesian filtering problem honest. During a quiet interval the Bayesian dealer (Bot 1) cannot tell "no arrival" from "arrival that declined" — the likelihood of a quiet interval is a **mixture** over both, i.e. a censored likelihood: with quotes fixed, visible fills are a thinned Poisson process with state-dependent rate `lambda_a · p_trade(v)`, `p_trade(v) = alpha · 1[v < b or v > a] + (1 − alpha) · f(h)`, so quiet over Δ contributes the factor `exp(−lambda_a · Δ · p_trade(v))` (§4.3). Without censoring, declines would leak V's location for free and the inference problem collapses.
3. **Gameplay.** Silence is information. If your quotes are wide and the market goes quiet, you cannot tell whether nobody came or everybody balked — and an informed trader declining tells you V is *inside* your quotes. Learning to read absence of flow is a skill the replay then makes legible ("look at everyone who walked").

### 1.5 Rounds, levels, and default parameters

- A round lasts **60 seconds** of game time. At round end, terminal inventory is marked at `V_T` (§2.1).
- Levels escalate `alpha` (the informed share); all other parameters stay fixed. The level table is **provisional until the playability gate (§5) selects the final regime**.

| Parameter | Symbol | Default | Unit | Notes |
| --- | --- | --- | --- | --- |
| Initial fair value | `V0` | 10_000 | ticks | $100.00; public at t = 0 |
| Round length | `T` | 60_000_000 | µs | 60 s |
| Jump intensity | `lambda_j` | 0.5 | jumps/s | ~30 jumps per round |
| Jump magnitude param | `p_J` | 0.2 | — | mean jump 5 ticks |
| Arrival intensity | `lambda_a` | 4.0 | arrivals/s | ~240 arrivals per round |
| Noise acceptance scale | `delta0` | 4.0 | ticks | `f(h) = exp(−h/delta0)` |
| Informed share, level 1–5 | `alpha` | 0.10 / 0.20 / 0.30 / 0.40 / 0.50 | — | provisional; gate-tuned |

All parameters live in one place in each engine (`sim/picked_off/params.py`; the web mirror) and inside each golden vector's `meta.params`.

---

## 2. Scoring — the exact accounting identity

### 2.1 Primitive accounting

Fills are indexed i = 1..N in time order. For fill i:

- `t_i` — fill time (µs); `p_i` — fill price (ticks); `q_i ∈ {+1, −1}` — dealer position change (§0);
- `b_i, a_i` — the dealer's quotes at the fill; `m_i = (a_i + b_i)/2` — quote mid (half-ticks allowed);
- `V_i = V(t_i)` — fair value at the fill.

Cash starts at 0 and inventory starts at 0. A customer buy (q = −1) adds `+a_i` to cash; a customer sell (q = +1) adds `−b_i`. So `cash_T = − Σ_i q_i · p_i` and `inv_T = Σ_i q_i`.

**Total PnL** marks terminal inventory at the final fair value:

```
PnL = cash_T + inv_T · V_T            (in ticks)
```

### 2.2 The decomposition

Three per-fill terms, each summed over all fills (computed in half-ticks so they are integers):

```
Spread captured     SC = Σ_i  q_i · (m_i − p_i)   = Σ_i (a_i − b_i)/2
Adverse selection   AS = Σ_i  q_i · (V_i − m_i)
Inventory cost      IC = Σ_i  q_i · (V_T − V_i)
```

**Identity (must hold exactly, every run):**

```
SC + AS + IC = Σ_i q_i · (m_i − p_i + V_i − m_i + V_T − V_i)
             = Σ_i q_i · (V_T − p_i)
             = inv_T · V_T  −  Σ_i q_i · p_i
             = inv_T · V_T  +  cash_T
             = PnL                                            ∎
```

The telescoping makes the identity an algebraic fact, independent of the model. It is enforced as a test invariant: **every** simulated round, in both engines, asserts `SC + AS + IC == 2·PnL` in half-ticks, as exact integer equality with no tolerance. The identity is itself a golden-vector check (§6).

Equivalent formula for the inventory term (also enforced as an exact test invariant):

```
IC = Σ_k  J_k · inv(t_k⁻)        summed over V jumps k after the first fill,
```

where `inv(t_k⁻)` is the dealer's inventory just before jump k. *Proof:* `Σ_i q_i (V_T − V_i) = Σ_i q_i Σ_{k: t_k > t_i} J_k = Σ_k J_k Σ_{i: t_i < t_k} q_i = Σ_k J_k · inv(t_k⁻)`. Inventory cost is exactly the exposure of standing inventory to subsequent fair-value jumps.

### 2.3 Interpretation — why these three names

- **Spread captured** is the revenue of the dealing franchise: half the posted spread on every fill, regardless of who filled you. It is **always ≥ 0** and is the only term the dealer fully controls.
- **Adverse selection** measures being picked off *at the moment of the fill*: how far true value already was past your mid, signed by the trade. Every informed fill contributes **strictly negatively** (an informed buy requires `V > a ≥ m + ½`, and q = −1 flips the sign; symmetrically for sells). Noise fills contribute mean-zero terms when your mid is an unbiased estimate of V. In the Glosten–Milgrom model this is where information costs you money, and it is realized entirely at the fill — informed traders know V *now*; they have no foresight about future jumps.
- **Inventory cost** is the PnL from fair-value jumps that occur *after* a fill, while the unit sits in inventory until round end. Because jumps are exogenous and independent of order flow, this term has **zero conditional mean** — it is pure risk, not drift. "Cost" is the conventional dealer name: it is the term whose *variance* punishes carrying inventory, and the reason an inventory-skewing dealer (Bot 2) accepts worse expected PnL per trade to flatten faster.

Per-fill attribution (`sc_i, as_i, ic_i`) is reported in the replay so the player can see, fill by fill, "you earned 3 half-ticks of spread but were 14 half-ticks behind fair value."

### 2.4 Markout diagnostics (NOT part of the identity)

For each fill and horizon `tau ∈ {1 s, 5 s}`:

```
MO_i(tau) = q_i · ( V(min(t_i + tau, T)) − p_i )      (ticks, integer)
```

Markouts are the standard empirical pick-off measure: fill price versus fair value a moment later, signed by the trade. `MO_i(0) = sc_i + as_i` (in tick terms), and because post-fill jumps are mean-zero here, `E[MO_i(tau)] = E[sc_i + as_i]` — the markout curve is flat in expectation, which is itself a model-validation test and a teaching plot in the writeup. Markouts at +1 s and +5 s are reported per fill in replay, research output, and golden vectors, but they are **diagnostics**: the exact identity of §2.2 is the score. (Two different horizons cannot both live inside one exact identity; see §9, decision D3.)

---

## 3. Engine — normative event loop

Both engines implement exactly this loop. Input: `params`, ordered `event_stream` (§6.2). Output: fills, declines (replay channel), terminal state, decomposition, markouts.

```
state:  V ← V0;  quotes ← unset;  cash ← 0;  inv ← 0
logs:   fills ← [];  declines ← [];  jumps ← []   (jumps kept for V(t) lookups)

for ev in event_stream:                  # strictly increasing ev.t_us, else abort
    if ev.type == "quote":               # bid/ask integers, ask ≥ bid + 1, else abort
        quotes ← (ev.bid, ev.ask)
    elif ev.type == "jump":              # ev.size ≠ 0
        V ← V + ev.size;  jumps.append(ev)
    elif ev.type == "arrival":           # quotes must be set, else abort
        (b, a) ← quotes;  h ← (a − b)/2
        if ev.trader == "informed":
            if   a < V:  fill(side="buy",  price=a)
            elif b > V:  fill(side="sell", price=b)
            else:        declines.append(t, "informed", reason="v_inside_quotes")
        else:  # noise
            if ev.u_accept < exp(−h/delta0):
                fill(side=ev.side_intent, price = a if buy else b)
            else:
                declines.append(t, "noise", side_intent, reason="balked_at_spread")

fill(side, price):
    q ← −1 if side == "buy" else +1
    cash ← cash − q·price;  inv ← inv + q
    fills.append(t, side, price, V, trader, b, a)     # V, quotes frozen at fill

at end of stream:
    V_T ← V
    PnL ← cash + inv · V_T
    compute SC, AS, IC per §2.2 (half-ticks);  assert SC + AS + IC == 2·PnL
    compute IC via jump formula;               assert equal
    compute markouts per §2.4 using jumps log
```

Live play emits two channels from the same loop: the **public feed** (fills, own quotes — what the UI shows during the round) and the **full log** (everything, incl. declines and the V path — unlocked for replay). Bots receive only the public feed (§4.1).

---

## 4. Bots

Bots are research instruments and live in the Python sim only (v1 web app does not ship bot opponents; see cut list). All bots implement a common interface and are forbidden access to V, trader types, declines, or the event stream — public feed only.

### 4.1 Common harness

- Callbacks: `on_start(params) → (bid, ask)`, `on_fill(t_us, side, price) → (bid, ask)`, `on_tick(t_us) → (bid, ask)`.
- `on_tick` fires on a fixed 10 Hz clock: `t = k · 100_000` µs for `k = 1..599` (not at t = 0 — `on_start` provides the opening quote there). Bots may change quotes **only** at these callbacks — this makes bot behavior exactly reproducible.
- **Quote injection rule.** A callback's returned quotes are spliced into the stream as a quote event stamped `decision time + 1 µs` (an `on_fill` triggered by an arrival at time t yields a quote event at t + 1). The generator's timestamp hygiene (§6.3 rule 5) guarantees no exogenous event ever occupies an injection slot, so strict monotonicity (§0 rule 2) holds in harness runs, the engine's assertion never fires, and an arrival at time t always trades against quotes set strictly before t. Fills can never coincide with a tick (arrival timestamps are kept off the tick grid), so `on_fill`/`on_tick` ordering at equal times never arises.
- The harness runs bots against generated streams: same exogenous stream (jumps, arrival times, types, side intents, uniforms) regardless of the bot's quotes. Outcomes differ only through the quotes — this enables paired comparisons with common random numbers (§5).

### 4.2 Bot 0 — fixed symmetric spread on the rolling tape mid

The naive baseline: no inference, just recentering on prints.

- `mid_est` = price of the **last fill**; `V0` before any fill.
- Quotes `bid = mid_est − k0`, `ask = mid_est + k0` with fixed half-spread `k0` (integer ticks, default 3; gate-tunable).
- Updates quotes after every fill and on every tick (idempotent between fills).

Bot 0 chases prints: a single noise fill at the ask drags its whole market up by construction, and it never widens when flow goes one-sided. It is *designed* to be picked off in informed regimes.

### 4.3 Bot 1 — Bayesian Glosten–Milgrom dealer

Maintains a grid posterior over V and quotes regret-free GM prices.

**Posterior.** `pi(v)` over the integer tick grid `v ∈ [V0 − W, V0 + W]`, `W = 200` ticks (covers > 5σ of total round V drift at defaults: per-jump RMS = √(E[J²]) ≈ 6.7 ticks, √30 jumps → ≈ 37 ticks round RMS). Initialized to a point mass at V0 (V0 is public, §1.1). After every update, renormalize; probability mass that convolves past the grid edge is truncated and renormalized (documented approximation, fine at W = 200).

**Time update** (jump-process transition over an interval Δ with no observation): with `mu = lambda_j · Δ`,

```
pi ← Σ_{k=0..K} Poisson(k; mu) · (D^{*k} * pi)
```

where `D` is the discrete-Laplace jump kernel of §1.1 and `D^{*k}` its k-fold self-convolution; `K` = smallest integer with `P(Poisson(mu) ≤ K) ≥ 1 − 1e−12` (at 10 Hz and `lambda_j = 0.5`, `mu = 0.05`, this gives **K = 6**: the upper tail past 6 is ≈ 1.5e−13). Direct truncated convolution is sufficient; numpy only.

**Observation updates.** Likelihood factors multiply into `pi` pointwise, with quotes (b, a) and `h = (a−b)/2` the bot's own standing quotes over the relevant interval:

- *Censored quiet interval* — at each tick, covering the elapsed interval Δ since the last update with **no visible fill**:

  ```
  L_quiet(v) = exp( − lambda_a · Δ · p_trade(v) )
  p_trade(v) = alpha · 1[v < b or v > a]  +  (1 − alpha) · f(h)
  ```

  This is the censoring term of §1.4: quiet is evidence that V is *inside* the quotes (where informed traders decline), with strength growing in `alpha` and Δ. Discretization note: this treats quotes and V's effect on thinning as constant across the 100 ms slice, applying the time update and the quiet factor sequentially per slice — the spec'd approximation, exact as Δ → 0; the writeup must state it.
- *Own fill* (the public tape and the bot's own fills are the same stream in a single-dealer market — the likelihood below is the "tape + own fills" update):

  ```
  buy at ask:   L(v) = alpha · 1[v > a] + (1 − alpha) · ½ · f(h)
  sell at bid:  L(v) = alpha · 1[v < b] + (1 − alpha) · ½ · f(h)
  ```

  applied at the fill's timestamp. Order of operations: time-update the elapsed sub-interval δ since the last update, multiply the quiet survival factor `L_quiet(v)` **for that same δ** (no visible fill occurred during it — the thinned-Poisson survival term), then multiply the fill factor. Dropping the pre-fill survival factor is not harmless: `p_trade(v)` differs by `alpha` between v inside and outside the quotes, so each fill would inject a likelihood-ratio error of up to `exp(lambda_a · δ · alpha)` (≈ 11% at defaults with δ = 100 ms), compounding over a ~240-arrival round into a posterior biased toward "V is outside my quotes".

**Quoting — GM regret-free prices.** Quotes satisfy the no-regret fixed point: the ask equals the posterior expectation of V *conditional on the next arrival lifting that ask*, and symmetrically for the bid:

```
E[V | buy at (b,a)]  =  ( alpha · Σ_{v>a} v·pi(v)  +  (1−alpha)·½·f(h) · Σ_v v·pi(v) )
                        / ( alpha · P_pi(v>a)      +  (1−alpha)·½·f(h) )
E[V | sell at (b,a)] =  symmetric with {v<b}
```

Deterministic fixed-point algorithm (integer quotes; ceil/floor keep the dealer on the profitable side of the conditional expectation):

```
a ← ceil(E_pi[V]) + 1;  b ← floor(E_pi[V]) − 1
repeat up to 50 times:
    a' ← max( ceil( E[V | buy  at (b,a)] ),  b + 1 )
    b' ← min( floor( E[V | sell at (b,a)] ), a' − 1 )
    if (a', b') == (a, b): stop                     # fixed point
    if (a', b') seen before: stop with the widest pair seen in the cycle
                                                    # (max ask, min bid) — conservative
    (a, b) ← (a', b')
```

Convergence is typically < 10 iterations with unimodal posteriors; the cycle rule makes the algorithm total and deterministic either way.

### 4.4 Bot 2 — Bot 1 + inventory skew (STRETCH, CUTTABLE)

Bot 1's quotes, both shifted by `−round(gamma · inv)` ticks (`gamma` default 0.5 ticks per unit), then re-clamped to `a ≥ b + 1`. Long inventory shades both quotes down to attract buyers and repel sellers. This trades expected PnL for inventory variance — the empirical comparison Bot 1 vs Bot 2 (same streams) is writeup material. **Cut without ceremony if the timebox bites.**

---

## 5. Playability gate (LOCKED DECISION)

**UI work (build step ④) does not start until a parameter regime exists in which Bot 1 beats Bot 0 by more than 30% mean PnL across ≥ 30 seeded runs.**

Precisely: a parameter set `(lambda_j, p_J, lambda_a, alpha, delta0, k0)` passes the gate iff, over N ≥ 30 paired rounds with common random numbers (same exogenous streams fed to both bots, §4.1):

```
mean PnL(Bot 0) > 0      and      mean PnL(Bot 1) ≥ 1.3 × mean PnL(Bot 0)
```

The `mean PnL(Bot 0) > 0` clause makes the ratio well-defined and meaningful — the baseline must itself be viable in the chosen regime, otherwise "beats by 30%" is vacuous (§9, decision D7). Report alongside (not part of the gate): bootstrap 95% CI of the paired mean difference, and the per-component decomposition means for both bots.

If no regime passes, tune `lambda_j`, `p_J` (jump size), `alpha`, `lambda_a` until one does, via the grid search in `sim/picked_off/gate.py` (results notebook: `notebooks/`). The passing regime becomes the level table of §1.5.

**Design principle (locked):** the game is tuned to the regime where information has value. If a Bayesian dealer reading the tape and the silences cannot meaningfully beat a fixed-spread chaser, the game's central skill isn't being rewarded and the parameters — not the thesis — are wrong.

---

## 6. Golden test vectors

### 6.1 Principles

- A vector is one JSON file: `{meta, event_stream, expected_output}`.
- The stream contains **only exogenous data**: V jumps, arrival times, trader types, noise side intents, acceptance uniforms — plus a **scripted quote schedule**. Quote events are part of the stream because fills are a function of quotes; without them, expected output would be undefined. In live play the same engine consumes player/bot quotes through the identical code path (§9, decision D4).
- Engines never draw randomness; the Python generator (`sim/picked_off/generator.py`) is the only RNG in the project. **No cross-language RNG, ever.**
- Both engines must reproduce `expected_output` from `(meta.params, event_stream)` with **exact integer equality** on every integer field.

### 6.2 JSON schema

Top level:

| Field | Type | Meaning |
| --- | --- | --- |
| `meta.schema_version` | int | This document specifies version **1**. |
| `meta.name` | string | Unique vector name, e.g. `"noise_only_tight_quotes"`. |
| `meta.description` | string | What the vector exercises. |
| `meta.seed` | int | Generator seed (provenance only; engines must not use it). |
| `meta.params` | object | Exactly the §1.5 table: `v0`, `round_us`, `lambda_j`, `p_jump`, `lambda_a`, `alpha`, `delta0`. |
| `event_stream` | array | Ordered events, strictly increasing `t_us`, each one of the three types below. |
| `expected_output` | object | See below. |

Event types (`t_us`: int µs, `0 ≤ t_us < round_us`):

| Event | Fields | Constraints |
| --- | --- | --- |
| quote | `{"t_us", "type": "quote", "bid": int, "ask": int}` | ticks; `ask ≥ bid + 1`; first stream event must be a quote at `t_us = 0` |
| jump | `{"t_us", "type": "jump", "size": int}` | ticks; `size ≠ 0` |
| arrival | `{"t_us", "type": "arrival", "trader": "informed"\|"noise", "side_intent": "buy"\|"sell"\|null, "u_accept": float\|null}` | `side_intent`/`u_accept` non-null **iff** `trader == "noise"` (informed side is endogenous — derived from V vs quotes; see §9, decision D5) |

`expected_output`:

| Field | Type | Meaning |
| --- | --- | --- |
| `fills` | array | Every fill, in order: `{"t_us", "side": "buy"\|"sell", "price": int ticks, "v_at_fill": int ticks, "trader", "markout_1s": int ticks, "markout_5s": int ticks}`. Side is customer-side (§0). Markouts per §2.4, clamped at round end. |
| `declines` | array | Every decline (the replay reveal): `{"t_us", "trader", "side_intent": ...\|null, "reason": "v_inside_quotes"\|"balked_at_spread"}`. |
| `v_terminal` | int | `V_T`, ticks. |
| `inventory_terminal` | int | units, signed. |
| `cash_terminal` | int | ticks. |
| `pnl_decomposition_half_ticks` | object | `{"total", "spread_captured", "adverse_selection", "inventory_cost"}` — **integers in half-ticks**; `total = spread_captured + adverse_selection + inventory_cost` exactly, and `total == 2 × (cash_terminal + inventory_terminal × v_terminal)`. |

Example (abridged but schema-complete):

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

(Walkthrough of the example: noise buy fills at ask 10003 with V = 10000, so q = −1, m = 10000, sc = 3 ticks = 6 half-ticks, as = q·(V−m) = 0, the −7 jump after the fill gives ic = q·(V_T − V_i) = (−1)·(−7) = +7 ticks = 14 half-ticks; PnL = cash + inv·V_T = 10003 − 9993 = 10 ticks = 20 half-ticks = 6 + 0 + 14. ✓ Markouts: V(1.4 s) = 10000 → mo_1s = (−1)·(10000 − 10003) = 3; V(5.4 s) = 9993 → mo_5s = (−1)·(9993 − 10003) = 10.)

This schema is duplicated verbatim in `vectors/SCHEMA.md` (kept in sync manually; DESIGN.md wins on conflict).

### 6.3 Cross-language determinism rules

1. All integer fields compare with exact equality. No tolerances anywhere.
2. The only float comparison in an engine is `u_accept < f(h)` (and `f` inside Bot 1, which is Python-only). Both engines compute `f(h) = exp(−h/delta0)` in IEEE-754 double precision. To make a 1-ulp `exp` discrepancy across languages harmless, the **generator certifies every vector**: it simulates the vector once and verifies `|u_accept − f(h)| > 1e−9` at every noise arrival as evaluated against the scripted quotes; if any margin fails, it re-rolls the seed. Engines may therefore compare naively.
3. JSON numbers: timestamps, prices, sizes are JSON integers; `u_accept` is a decimal float with ≤ 17 significant digits (round-trips exactly as an IEEE double).
4. Engines must validate streams (monotone timestamps, quote-before-arrival, field constraints) and fail loudly — a malformed vector is a bug, not an input to tolerate.
5. **Timestamp hygiene** (so run-time quote injection can never tie, §4.1): the generator re-draws any **jump or arrival** whose timestamp (a) is ≤ 1 µs, (b) lands on a multiple of 100_000 µs or 1 µs after one (the bot tick grid and its injection slots), or (c) is within 1 µs of another exogenous event (this reserves every fill-time + 1 slot). Certified vectors inherit these guarantees; engines still assert only plain strict monotonicity.

### 6.4 Planned vector inventory (built in step ②)

At minimum: empty round (no arrivals — identity holds at all-zeros); noise-only round; informed-only round; jump-heavy round; declines-only (wide quotes); quote-changes-mid-round; markout-clamping at round end (fill < 5 s before T); negative-inventory round; long round-trip inventory; one maximal "kitchen sink" round at default params. Each vector's `expected_output` is produced by the Python engine and **reviewed by hand once** before being frozen.

---

## 7. Engineering

### 7.1 Repository layout (monorepo)

```
picked-off/
├── DESIGN.md                  ← this file; source of truth
├── README.md                  ← pitch, status, replay GIF placeholder
├── LICENSE                    ← MIT
├── .gitignore
├── sim/                       ← Python 3.11+; numpy only for core; pytest
│   ├── pyproject.toml
│   ├── picked_off/
│   │   ├── __init__.py
│   │   ├── params.py          ← parameter dataclass + level table (single home for defaults)
│   │   ├── events.py          ← event types, stream parsing/validation
│   │   ├── engine.py          ← the §3 event loop
│   │   ├── scoring.py         ← §2 decomposition, markouts, identity assertions
│   │   ├── generator.py       ← seeded stream generation; the ONLY RNG; vector certification (§6.3)
│   │   ├── vectors.py         ← golden vector I/O, schema validation, conformance checking
│   │   ├── gate.py            ← playability-gate runner: paired seeded runs, parameter grid (§5)
│   │   └── bots/
│   │       ├── __init__.py
│   │       ├── base.py        ← §4.1 interface + harness
│   │       ├── bot0.py        ← §4.2
│   │       ├── bot1.py        ← §4.3
│   │       └── bot2.py        ← §4.4 (stretch)
│   └── tests/
│       ├── test_identity.py   ← SC + AS + IC == PnL, exact, on randomized streams
│       └── test_vectors.py    ← every vectors/*.json reproduces byte-exact
├── web/                       ← React + TS + Vite; Canvas/SVG; no game-engine lib
│   └── (vite react-ts default now; engine port in web/src/engine/ in step ④,
│        vitest conformance suite over ../vectors in step ④)
├── vectors/
│   └── SCHEMA.md              ← §6.2 duplicated; golden *.json land here in step ②
├── notebooks/                 ← gate grid-search results, analysis (step ③)
└── writeup/                   ← research writeup (step ⑤)
```

### 7.2 Python sim

- Python ≥ 3.11. Core dependencies: **numpy only**. Dev: pytest. No pandas/scipy in `picked_off/` (notebooks may use anything).
- The sim is the **source of truth**: vectors are generated and certified here; the web engine conforms to them, never the reverse.

### 7.3 Web app

- React + TypeScript + Vite. Rendering via Canvas/SVG directly — no game engine, no chart library for the core play screen.
- The TS engine (`web/src/engine/`, step ④) is a line-for-line port of §3 with the same integer semantics, tested in vitest against the same `vectors/*.json` files.
- **Aesthetic:** minimalist grey trading terminal. Monochrome panel, tabular numerals, thin rules; color reserved for fills and PnL.
- **Controls:** bid and ask are horizontal lines on the price canvas, draggable by touch or mouse (fat hit targets; mobile-friendly). No keyboard required to play.
- **Round flow:** set opening quotes → 60 s live round (censored feed) → score screen with decomposition → replay screen (decline reveal, V path overlay, per-fill markouts).
- **Live round source:** the browser never draws randomness (§0 rule 3 holds in the web too). Live rounds consume pre-generated, generator-certified streams shipped as static assets with the site; the TS engine replays them exactly as it replays golden vectors. Player quote drags become quote events stamped at the smallest unoccupied µs strictly after their game-time decision instant, mirroring §4.1's injection rule (the search terminates immediately because hygiene rule §6.3-5c forbids consecutive-µs exogenous events).
- **Session export:** a "Download my session" button serializes the full round — params, every player quote event, every fill, the revealed stream, the decomposition — as a JSON file, client-side (`Blob` + download). **No backend ever**; no telemetry; localStorage at most for settings.

### 7.4 Deploy

Vercel static hosting of `web/` build output. No server-side anything (see cut list).

### 7.5 Cut list (LOCKED)

**No multiplayer. No server. No order-book depth. No latency model.** Additionally cut for v1: bot opponents in the web app (bots are sim-side research instruments), inventory hard caps, multi-unit fills. Bot 2 is stretch and cuttable (§4.4).

---

## 8. Build sequence and timebox

Four weeks, one step per week after this one. Each step has a hard "done" gate.

| Step | Deliverable | Done when |
| --- | --- | --- |
| ① Scaffold + spec | this repo skeleton, DESIGN.md | tree exists; DESIGN.md implementable by a stranger |
| ② Sim + vectors (wk 1) | engine, scoring, generator, ≥ 10 certified vectors | `pytest` green: identity exact on randomized streams; all vectors reproduce byte-exact |
| ③ Bots + gate (wk 2) | Bot 0, Bot 1 (+ Bot 2 stretch), grid search | playability gate (§5) passes; level table finalized; gate notebook committed |
| ④ Web game (wk 3) | TS engine port + play screen | vitest green on the same vectors; a 60 s round is playable on a phone |
| ⑤ Polish (wk 4) | replay screen, README GIF, writeup, deploy | replay reveals declines over V path; writeup analyzes Bot 0/1 (decomposition + optimal-spread-vs-alpha); live Vercel URL |

UI work is gated behind ③ per §5 — locked.

---

## 9. Decision log and open questions

Resolved decisions (the prompt-level ambiguities each choice settles):

- **D1 — Noise elasticity reference.** "Distance from mid" = the dealer's own quote mid, so `f` depends only on the half-spread (§1.3). Keeps noise flow exogenous to V; mispricing is punished exclusively by informed flow. Rejected variant: distance from a tape-derived reference mid (would punish off-tape quoting but contaminates Bot 1's likelihood and adds a free V-signal).
- **D2 — Decomposition term boundaries.** Spread captured is measured against the dealer's **own mid** (always ≥ 0); adverse selection is mid-vs-V **at the fill**; inventory cost is V-moves **after the fill** to terminal. "Fill price vs V at fill" from the project brief equals SC + AS combined; splitting at the mid is what makes SC sign-definite and AS purely informational. All three brief timestamps (fill-time V, post-fill moves, terminal marking) appear, assigned to the terms that keep the identity exact and the interpretations clean.
- **D3 — Markouts are diagnostics.** Two horizons (+1 s, +5 s) cannot both be terms of one exact identity, so markouts are reported per fill but excluded from the score (§2.4).
- **D4 — Quote events live in the vector stream.** Expected output is undefined without the dealer's quotes, so golden vectors script them as first-class events; live play feeds player/bot quotes through the identical engine path (§6.1).
- **D5 — `side_intent` is null for informed arrivals.** An informed trader's side is endogenous (determined by V vs quotes), so the stream pre-draws side only for noise traders (§6.2).
- **D6 — V0 is public.** Both player and bots know V exactly at t = 0 (§1.1). Without a public anchor the first seconds are unlearnable noise and priors are arbitrary.
- **D7 — Gate ratio guard.** The >30% gate additionally requires Bot 0's mean PnL > 0, otherwise the ratio is ill-defined or vacuous (§5).
- **D8 — Quotes persist after fills** (no depletion or re-arm delay); one unit per fill (§1.2).
- **D9 — Integer time/price domain.** Integer µs and ticks; discrete-Laplace jumps; half-tick scoring — chosen so the identity and vector conformance are exact, with no float tolerance anywhere (§0, §6.3).
- **D10 — Bots are sim-only in v1** (§4, §7.5).
- **D11 — Run-time quote injection is decision-time + 1 µs, backed by generator timestamp hygiene.** Bot and player quote decisions become quote events at the smallest unoccupied µs strictly after the decision (exactly +1 µs for bots); the generator keeps jumps/arrivals off t ≤ 1, off the 10 Hz tick grid and its +1 slots, and never at consecutive µs (§4.1, §6.3 rule 5). This keeps §0 rule 2's strict monotonicity literally true in every run mode — vectors, bot harness, and live play — with no tie-breaking rules anywhere.
- **D12 — Live web rounds replay pre-generated streams.** The no-RNG rule extends to the browser: the static site ships a pool of certified streams produced by the Python generator at build time (§7.3). No backend, no cross-language RNG, and every live round is exportable and bit-replayable by construction.

Open questions (deferred, non-blocking; revisit at the step where they bite):

- **Q1 (step ③):** Should the gate also require Bot 1 ≥ Bot 0 on *median* PnL, to guard against a regime where Bot 1's mean is carried by a few lucky tails?
- **Q2 (step ③):** Bot 0's last-trade mid is maximally naive. If the gate passes trivially at all α, consider an EWMA-mid Bot 0 variant as the "fair" baseline and report both.
- **Q3 (step ④):** Whether the live tape should show fill side (color) or price only — side display materially changes the human inference game. Decide in playtesting.
- **Q4 (step ⑤):** Whether replay should show Bot 1's posterior ribbon as a "ghost" overlay (teaching tool vs scope creep).
- **Q5 (step ②):** Whether V < 0 needs clamping at extreme parameter corners during gate grid search (engine currently does not clamp; generator can simply reject such corners).
