# Picked Off: making markets against anonymous toxic flow

*A playable Glosten–Milgrom study — simulator, calibrated game, Bayesian benchmark, and an n=3 self-experiment. 3-minute read; everything reproducible from the repo.*

## 1. Why this game

In US equities, a retail market maker can largely *buy* uninformed flow: payment for order flow, broker segmentation, and flow labeling sort the toxic from the harmless before a quote is ever touched. **Crypto market making has no such luxury.** Flow on an exchange is anonymous and unsegmented — the arb bot that just read a price move on another venue hits the same book as the tourist. A crypto MM cannot purchase adverse-selection protection; they must *infer toxicity from the tape itself*, in real time, and price it into the spread.

Glosten–Milgrom (1985) is the cleanest abstraction of exactly that problem: a dealer quotes bid/ask against a mix of noise traders and traders who know the true value, and every fill is a Bayesian signal. Picked Off makes the abstraction playable — including the part everyone forgets: **the customers who decline to trade are information too**, and real dealers never see them.

*Honest caveat:* real "informed" flow has a speed or inference edge inside an order book, not oracle knowledge of a hidden value. GM's oracle trader is a deliberate idealization that isolates the mechanism (stale quotes get billed) from the microstructure that produces it.

## 2. The model and the exact identity

Hidden value `V`: pure jump process (Poisson times, discrete-Laplace sizes), flat between jumps. Poisson arrivals are informed w.p. α — they trade only strictly through `V`, else walk away *invisibly* — or noise, accepting with probability `exp(−half-spread/δ₀)`. One unit per fill; single dealer. All prices are integer ticks and all times integer microseconds, so the decomposition

```text
total PnL  =  spread captured  +  adverse selection  +  inventory cost
              Σ q·(m−p)           Σ q·(V_fill−m)        Σ q·(V_T−V_fill)
```

is an *algebraic identity*, asserted as exact integer equality on every round in both engines (Python sim = source of truth; the TypeScript game engine reproduces 12 frozen golden vectors exactly — and, it turned out, live human sessions too; §5). Full spec: [DESIGN.md](../DESIGN.md).

## 3. Calibration: where does information pay?

The game's levels were chosen by a **playability gate**: a parameter regime qualifies only if a Bayesian dealer (Bot 1) beats a naive fixed-spread dealer (Bot 0) by >30% mean PnL over 30 paired seeded rounds, with Bot 0 still profitable. Over a 72-regime grid, **8 passed** ([full table](../notebooks/gate_results.csv)); the shipped regime (`λ_jump=0.2/s, δ₀=8, k₀=2`) gives the cleanest ramp (mean ticks/round):

| Level | α | Bot 0 (naive) | Bot 1 (Bayesian) | edge |
| --- | --- | --- | --- | --- |
| 1 | 0.10 | 144.8 | 114.5 | 0.79× |
| 2 | 0.20 | 85.9 | 86.8 | 1.01× |
| 3 | 0.30 | 69.4 | 93.7 | 1.35× |
| 4 | 0.40 | 35.1 | 61.1 | 1.74× |
| 5 | 0.50 | 18.2 | 55.6 | 3.05× |

**Finding:** information processing is worth more when flow is more toxic — and *naive quoting is rational at low α*. Bot 1's regret-free quotes are zero-expected-edge by construction (the GM theorem), so when almost nobody is informed, a wide dumb spread simply out-earns it. The 0.79× is not a bug; it is the point.

## 4. Mechanism

Decomposition of the same paired runs: Bot 1 wins by (a) **losing less to adverse selection** — it updates on fills *and on censored quiet intervals* (silence at high α means V is probably inside your quotes), and (b) **capturing more spread at high α** — it widens when uncertain, monetizing noise without standing stale. Inventory cost is mean-≈0 for both bots, as theory predicts when jumps are independent of flow. Statistical honesty: the gate is means-based per spec; the paired-difference 95% CI is positive at L4 ([0.3, 50.0]) and L5 ([13.6, 63.1]) but straddles zero at L3 ([−7.5, 53.2]) at n=30.

## 5. Human vs bot (n=3 self-experiment)

The game exports full sessions; [notebooks/human_vs_bot.ipynb](../notebooks/human_vs_bot.ipynb) ingests any session JSONs dropped into `sessions/` and replays them through the Python engine. Current corpus: three rounds by the author — framed honestly as an illustration of the instrument, not evidence.

- **Validation first:** all three web sessions reproduce **bit-exactly** in the Python engine — the cross-language contract holds on live rounds, not just frozen vectors.
- **L1: human 481, bot 203.** Wide quoting harvested noise; the bot's zero-edge prices left money on the table. The gate's prediction, played out by hand.
- **L5, round 1: human 388, bot 196.** The human tracked value nearly as well as the bot (time-weighted mid-vs-V error 2.7 vs 1.9 ticks, re-anchoring within ~6 s of jumps) while quoting wider. Skill or luck — n=1.
- **L5, round 2: human −872, bot +60.** A pure repricing failure: after **all eight** ≥5-tick jumps, the human's mid *never* returned to within 5 ticks of value (tracking error 18.8 ticks vs 3.4). Informed flow billed the stale quotes −2403 ticks of adverse selection across 207 fills.
- **Style gap:** human ~16–38 quote updates/round; bot ~180–240. Human edge (when present) = spread selection; bot edge = relentless recentering. The hybrid is untested.

## 6. Limitations and future work

**Limitations.** Single dealer (no quote competition — spreads are not competed down); no order-book depth (one unit per fill); informed traders know `V` exactly (an upper bound on toxicity per arrival); noise demand depends only on the spread, not on placement vs. consensus; α is constant within a round.

**Future work.** The environment is deterministic given a seed, integer-exact, fast (~ms/round in Python without the Bayesian bot), and ships with a verified PnL decomposition — i.e., **RL-ready**. The interesting regimes are precisely where GM's closed-form intuition breaks: inventory limits (where the skew/spread trade-off binds), competing dealers (where the regret-free price war begins), and drifting α (where toxicity must be tracked, not assumed). Bot 1 provides the natural baseline to beat; Bot 2 (inventory-skewed) is implemented and unstudied. Contributions of session data welcome — drop an export into `sessions/` and the notebook does the rest.

---

*Engines and methodology: [DESIGN.md](../DESIGN.md) · gate detail: [REPORT2.md](../REPORT2.md) · web build: [REPORT3.md](../REPORT3.md) · play it: [picked-off.vercel.app](https://picked-off.vercel.app)*
