# REPORT5 — Home screen, routing, back-navigation, rough-edge sweep

Date: 2026-06-13. Engines frozen (no diffs under `sim/picked_off` or `web/src/engine/`); 236 pytest + 25 vitest green; eslint clean. UI/navigation only.

## Routes map

| Path | Screen | Cold load / refresh behavior |
| --- | --- | --- |
| `/` | Home (new entry point) | First-ever visit redirects to `/tutorial` (replace), lands back after |
| `/levels` | Level select | Always available |
| `/play/:level` (1–5) | Live round | Starts a **fresh** round for that level; level mismatch or finished round also restarts |
| `/tutorial` | Scripted practice round | Restarts the tutorial |
| `/score` | Score screen | No round state → redirect home (replace), no crash |
| `/replay` | Replay screen | Same guard as `/score` |
| anything else | — | Resolves to home (never a blank screen) |

Routing is a hand-rolled history-API mini-router ([web/src/router.ts](web/src/router.ts), ~50 lines) — no dependency added; full control over the back-guard semantics below. Vercel serves deep links via the SPA rewrite added to [vercel.json](vercel.json) (filesystem matches — assets, streams — are served first; everything else falls back to `index.html`).

## What changed

1. **Home screen** ([HomeScreen.tsx](web/src/ui/HomeScreen.tsx)) — title, the one-line pitch, PLAY → `/levels`, HOW IT WORKS → `/tutorial`, quiet footer links (writeup, GitHub). Level select's masthead became "PICK A LEVEL" (home owns the title now).
2. **Back navigation.**
   - Browser back during a **live round**: the pop is cancelled (re-push), the round **freezes** (game clock, input, and event processing all hold — the freeze shares the tutorial-card pause mechanism in LiveScreen), and a terminal-styled dialog asks *"Leave the round? It counts as abandoned."* Stay → clock resumes exactly where it froze; Leave → round discarded, navigation proceeds (replace, so the history stays clean).
   - Back during the **tutorial**: leaves freely (it's practice; the explicit `←` acts as skip and marks the tutorial done).
   - `← Home` affordance on every screen: HUD `←` button in live/tutorial (routes through the same confirm flow), `← Home` links on levels/score, Home buttons added to score and replay button rows.
   - After a round, `/score` **replaces** the `/play` history entry — back from the score screen goes to levels, never into a dead round.
3. **Rough-edge sweep** (REPORT3 §Rough edges):
   - (a) Replay decline-marker clutter at L4/L5 — confirmed real (~100+ walk-away markers). Added an **All / Pick-offs-only** toggle in the replay controls; defaults to pick-offs-only at L4–L5, all-markers at L1–L3; legend text adapts.
   - (b) Key-hint overlap — the `shift ±5` hint moved from the canvas bottom edge into the HUD (DOM), eliminating the only overlap case; per-line `W/S`/`P/L` hints sit beside the label boxes and were verified non-overlapping by construction at 390 px.
   - (c) Session re-export 1-ulp caveat — left as documented (REPORT3 §8); no code.
4. **Self-review catches** (fixed before ship): the LiveScreen React key previously incorporated mutable round state, so opening the leave-dialog mid-round would have remounted the screen and reset the clock — now keyed by a monotonic round id; `/play/:level` cold starts also re-key correctly.

## Verification (per budget)

- `npm run build` ✓ · vitest 25/25 ✓ · pytest 236/236 ✓ · eslint clean ✓ · one self-review pass (above).
- Post-deploy checks below (deep links + round-critical assets). A human click-through of one full round is the next step — that is the playtest, per plan.

## Deferred

- Replay marker toggle does not declutter overlapping *fills* (only decline markers); fills are the data, leaving them.
- No transition animations between routes; instant cuts fit the terminal aesthetic and the budget.
- Tutorial-leave via browser-back does not mark the tutorial done (explicit skip/`←` does) — deliberate: an accidental back shouldn't suppress first-visit onboarding.
