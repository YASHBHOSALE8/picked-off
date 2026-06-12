# REPORT4 — Final session: polish, onboarding, writeup, publish

Date: 2026-06-13. Engines frozen (zero diffs in `sim/picked_off/*.py` engine/scoring code and `web/src/engine/`); pytest 236 ✓, vitest 25 ✓ after every change.

## What shipped

1. **Keyboard quote control** — W/S (ask), P/L (bid), ±1 tick, hold-to-repeat (native key-repeat), Shift = ±5. Identical engine path as dragging (the shared `applyQuotes` → D11 injection). Key map isolated in [web/src/ui/keys.ts](web/src/ui/keys.ts) for remapping. On-screen hints render next to each quote line on fine-pointer devices only (hidden on touch).
2. **Onboarding layer**
   - **First-visit tutorial** (~30 s, skippable, never reappears after completion — `localStorage`; replayable via "? replay the 30s tutorial" on the level screen). Runs a dedicated scripted stream ([streams/tutorial.json](web/public/streams/tutorial.json), hand-choreographed and certified with the frozen generator's hygiene + V>0 rules by [build_tutorial_stream.py](web/scripts/build_tutorial_stream.py)): four guaranteed noise fills with "that's spread income" cards, a hidden +12 jump, then exactly one informed arrival → **"That trader knew something you didn't. You just got picked off."** If the player's quotes happen to dodge it, a fallback card teaches the silence lesson instead. Closing card: "Real rounds mix both kinds — and you can't tell who's who." Cards pause the game clock; the tutorial then flows into the normal score screen.
   - **"What's going on?"** — a "?" toggle during play with five one-liners (lines, dots, the silence, position, α).
   - **Score-screen interpretations** — sign-aware plain-English one-liners under each component (e.g. "Informed traders took $X from you over N pick-offs — the value had already moved when they hit your quote").
3. **Research writeup** — [writeup/writeup.md](writeup/writeup.md), 3-minute quant-screener read: crypto framing (anonymous unsegmented flow ⇒ toxicity must be inferred, GM as the clean abstraction, with the honest oracle-trader caveat), model + exact identity, the gate's 8/72 results and 0.79×→3.05× edge ramp, mechanism (less AS + smarter widening; IC mean-zero; L3 CI caveat stated), human-vs-bot (below), limitations + RL-ready future work.
4. **Human-vs-bot notebook** — [notebooks/human_vs_bot.ipynb](notebooks/human_vs_bot.ipynb), executed end-to-end, ingests anything dropped into `sessions/` (currently the author's 3 exports: one L1, two L5).
5. **README final pass** — crypto pitch, PLAY link, 3-line how-to, gate table, writeup/DESIGN links, topics.
6. **Replay GIF** — generated programmatically: [docs/render_replay_gif.py](docs/render_replay_gif.py) replays a real L4 round (Bot 1 as dealer) through the Python engine and renders 72 frames in the game palette → [docs/replay.gif](docs/replay.gif) (0.4 MB). It is a *stylized render of the replay screen's content*, not a pixel screen-capture (Playwright would have needed a ~120 MB browser install); swap in a real recording whenever you like.

## Human-vs-bot findings (n=3 self-experiment, honestly framed)

- **Cross-engine validation:** all three web sessions replay **bit-exactly** through the Python engine — the shared-vector contract holds on live human rounds (the theoretical 1-ulp `u_accept` divergence never occurred).
- **L1-605045:** human **+481** vs Bot 1 **+203** ticks — wide quoting harvested noise; the gate's "naive play wins at low α" prediction, played by hand.
- **L5-1037333:** human **+388** vs **+196** — the human tracked value nearly as well as the bot (time-weighted |mid−V| 2.7 vs 1.9 ticks) while quoting wider.
- **L5-1038342:** human **−872** vs **+60** — a pure repricing failure: after all **eight** ≥5-tick jumps the human's mid never returned to within 5 ticks of value (tracking error 18.8 vs 3.4 ticks); adverse selection −2403 ticks over 207 fills.
- **Style gap:** human 16–38 quote updates/round vs bot ~180–240. Human edge = spread selection; bot edge = relentless recentering.

## Ship status

- **Live:** <https://picked-off.vercel.app> (deployed this session; tutorial stream included — pool is now 200 + 1 streams).
- **Repo:** <https://github.com/YASHBHOSALE8/picked-off> — flipped **PUBLIC** this session; topics added (market-making, glosten-milgrom, adverse-selection, market-microstructure, trading-game).
- **Auto-deploy:** GitHub→Vercel connection was made and verified in the previous session (REPORT4-deploy.md); this session's final push re-exercises it.

## Left for you manually

1. Nothing blocking. Optional: replace [docs/replay.gif](docs/replay.gif) with a true screen recording of the replay UI if you prefer pixels over the render.
2. Playtest pass over REPORT3's rough-edge list (now plus: tutorial copy tone, key-repeat feel) — that was always the post-ship plan.
3. Future sessions: drop exports into `sessions/`, re-run the notebook.
