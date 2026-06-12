# Picked Off

**A market-making game about adverse selection.** You are the only dealer in the market. You post a bid and an ask; anonymous orders arrive and trade at your prices — or walk away without a word. Most of the flow is noise. Some of it knows *exactly* what the asset is worth, and it only ever trades when your quote is wrong. You can't tell who is who: every fill might be income, or it might be the moment you got picked off. Your score is decomposed exactly into the three forces that rule a dealer's life — **spread captured**, **adverse selection**, **inventory cost** — and the post-round replay reveals the hidden fair value, every trader who exploited you, and every one who looked at your spread and declined. Silence, it turns out, was information all along.

**Status: playable** — steps ①–④ of ⑤ complete (spec → Python sim → bots/gate → web game). Polish + writeup in progress.

> **[SCREENSHOT PLACEHOLDER — live round, grey terminal, two quote lines + fill flashes. Replace me.]**
>
> **[REPLAY GIF PLACEHOLDER — `docs/replay.gif`: scrubbing the reveal, V path + red pick-off rings. Replace me.]**

## How to play

1. Pick a level (1–5). The level sets **α** — the share of arriving traders who know the true value.
2. Set your opening bid/ask by dragging the two lines, then start the 60-second clock.
3. The fair value starts public at $100.00, then jumps invisibly. Fills flash on the tape (color = side). Declines are invisible — a quiet market means *either* nobody came *or* everyone who came refused to trade with you. Those are very different things.
4. Drag your quotes anytime: tighter spread → more noise fills, more spread income; but a quote on the wrong side of the true value is free money for the informed.
5. At the close, your inventory is marked at the final fair value and your PnL is split exactly into spread captured + adverse selection + inventory cost.
6. **Watch the replay.** The white line is what the value really did. Red rings are the fills that picked you off. Red squares are informed traders who *declined* — your spread straddled the truth and they walked. Grey ×'s balked at your spread. Tap any fill for its full anatomy, markouts included.
7. "Download my session" exports the entire round as JSON, client-side. No backend, no telemetry, ever.

## The model (one paragraph)

Glosten–Milgrom (1985) with a pure-jump hidden value: V jumps at Poisson times with discrete-Laplace sizes and is flat in between. Orders arrive Poisson; each is informed with probability α (trades only strictly through the true value, else declines) or noise (random side, accepts with probability `exp(−half-spread/δ₀)`). One unit per fill, single dealer, no book depth. Everything is integer ticks and microseconds, so the accounting identity *spread + adverse selection + inventory = total PnL* holds **exactly** — it's a test, not a rounding hope. The Python simulator is the source of truth; this web engine reproduces 12 frozen golden test vectors with exact integer equality. The full spec is [DESIGN.md](DESIGN.md); implementation reports are [REPORT2.md](REPORT2.md) and [REPORT3.md](REPORT3.md).

## Why these levels (the honest numbers)

The game is tuned so that *information has value*: levels were chosen by a "playability gate" — a Bayesian dealer (reads the tape **and the silences**) must beat a naive fixed-spread dealer by >30% mean PnL over 30 paired seeded rounds. Results at the final regime (mean ticks/round; full grid in [notebooks/gate_results.csv](notebooks/gate_results.csv)):

| Level | α | naive bot | Bayesian bot | edge | gate |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.10 | 144.8 | 114.5 | 0.79× | — naive play genuinely wins |
| 2 | 0.20 | 85.9 | 86.8 | 1.01× | — parity |
| 3 | 0.30 | 69.4 | 93.7 | 1.35× | PASS |
| 4 | 0.40 | 35.1 | 61.1 | 1.74× | PASS |
| 5 | 0.50 | 18.2 | 55.6 | 3.05× | PASS |

That 0.79× at level 1 is not a bug: when almost nobody is informed, zero-edge "regret-free" quoting leaves money on the table — wide spreads print. By level 5, spread income alone cannot survive the toxicity. That arc *is* the game.

## Repository

| Path | What |
| --- | --- |
| [DESIGN.md](DESIGN.md) | The spec; source of truth (v1.1, changelog §10) |
| [sim/](sim/) | Python simulator — canonical engine, Bayesian bots, gate (236 tests) |
| [web/](web/) | React + TS + Vite game; TS engine port verified against the same vectors |
| [vectors/](vectors/) | 12 frozen golden test vectors consumed by both engines |
| [notebooks/](notebooks/) | Playability-gate grid search results |
| [writeup/](writeup/) | Research writeup (step ⑤) |

## Develop

```bash
cd sim && python -m pytest         # Python engine: 236 tests
cd web && npm install
npm test                           # TS engine: 25 conformance tests vs ../vectors
npm run dev                        # play locally
npm run build                      # static build (deploys to Vercel as-is)
```

MIT — see [LICENSE](LICENSE).
