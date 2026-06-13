# REPORT6 — On-screen touch quote buttons

Date: 2026-06-14. Engines frozen (zero diffs under `sim/` and `web/src/engine/`; verified by `git diff --stat`). 236 pytest + 25 vitest green, `npm run build` ✓, eslint clean. Files touched: `web/src/ui/LiveScreen.tsx`, `web/src/ui/keys.ts`, `web/src/index.css`.

## What changed

Four borderless white-arrow nudge buttons on the live-round screen, shown **only on coarse-pointer devices** and hidden on desktop — gated by `touchControls = !hasFinePointer()`, the exact inverse of the existing key-hint auto-hide (`hasFinePointer()` drives the W/S · P/L hints). A device whose primary pointer is fine (desktop, touch-laptop with trackpad) gets keys + hints and no pads; a phone/tablet gets pads and no hints.

### Placement (≈390px portrait)

```text
┌──────────────────────────────────────────────┐
│ 0:42  L3  pos +1  spread captured +$0.18  ?   │  ← HUD (top row, unchanged)
├──────────────────────────────────────────────┤
│                                                │
│            price canvas · quote lines          │
│              · fills · (drag still works)      │
│                                                │
│   ▲                                      ▲     │
│  ASK                                    BID    │  ← bottom corners
│   ▼                                      ▼     │
└──────────────────────────────────────────────┘
```

- **Bottom-left = ASK**, **bottom-right = BID**, mirroring the keyboard's two-handed split (W/S on the left, P/L on the right). Each cluster is `▲ / label / ▼` stacked.
- HUD readouts (clock, level, position, PnL ticker) live in the separate top flex row — no overlap with the bottom-corner pads. The pads sit only during the running clock (the arm overlay owns the bottom strip pre-start), so no clash there either.
- Styling: `▲ ▼` glyphs in near-white (`--v` = #e8e9ea), **no background, no border**; 60×46px hit area (≥44px) around each borderless glyph; pressed-state flick via `opacity: 0.5; transform: scale(0.85)` (90ms) — no color beyond white. The container is `pointer-events: none` so taps between the buttons fall through to the canvas; only the buttons capture.

### Behavior

- **Tap = ±1 tick** on that quote; **press-and-hold = repeat** (300ms delay, then every 70ms — constants `KEY_HOLD_DELAY_MS` / `KEY_HOLD_REPEAT_MS` in `keys.ts`).
- Every adjustment goes through the **same engine path as dragging and keys**: keyboard and pads now both call a single `nudge(dir, step)` → `applyQuotes` → `round.setQuotes(…, gameT())`, i.e. the D11 +1µs injection rule. No new quote logic was added; the keyboard handler was refactored onto `nudge` so the two literally share it. The draggable lines and the buttons mutate the same `round` state and stay in sync.
- Pads respect the pause system: `nudge` no-ops while a tutorial card or the leave-round dialog holds the clock, and the pads hide (clearing any held interval) whenever the round is paused/frozen.
- Robustness: pointer-capture on press means a finger that slides off the glyph still releases the hold on lift; `onPointerCancel` and an unmount effect also clear holds; clamped nudges (ask at bid+1) become no-ops in `setQuotes`, so holding into a clamp emits no quote-event flood.

## Verification (per the stated budget)

- `npm run build` ✓ · vitest 25/25 ✓ · pytest 236/236 ✓ · eslint clean ✓ · one self-review pass (shared-path, pause integration, cleanup, layout — all confirmed).
- Production deployed and the **deployed bundle hash matches the local build** (`index-C9YwadV2.js`) and contains the pad markup (`quote-pads`, `pad-btn`, `setPointerCapture`); `/` returns 200.
- Desktop "no buttons" is guaranteed structurally by the same media query that already (correctly) shows key hints on desktop today.

## Deferred / notes

- **Touch-emulated click-through was not run here** — no headless browser is installed (a ~120MB Playwright/Chromium install was deliberately avoided in prior sessions). The media-query gate and pointer logic are verified by build + self-review; the actual touch feel (tap vs hold cadence, thumb reach) is exactly what the planned **human playtest** covers.
- Pads are shown during the running clock only; opening quotes pre-start are still set by dragging on touch (the arm overlay occupies the bottom strip). Could add arm-phase pads later if playtest wants them.
- The bottom-right BID cluster sits near the canvas's right-edge price labels; white arrows over dim labels remain readable, but if it reads cluttered in playtest, nudge the price-label x-inset left by ~60px.
- Hold cadence approximates native OS key-repeat (which has no JS timer to literally reuse); both now read from the same `keys.ts` constants for one-place tuning.
