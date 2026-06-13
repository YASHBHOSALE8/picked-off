# REPORT7 — Mobile quote buttons: larger + inset

Date: 2026-06-14. **CSS-only** change (`web/src/index.css` is the sole modified file — verified by `git status`). Engines and all TS/TSX frozen. 236 pytest + 25 vitest green, build ✓, eslint clean.

## New dimensions & placement

All values are `:root` CSS custom properties co-located with the `.quote-pads` rules — tweak in one place, no rebuild logic.

| Property | Constant | Was | Now |
| --- | --- | --- | --- |
| Hit-area width | `--pad-btn-w` | 60px | **132px** (2.2×) |
| Hit-area height | `--pad-btn-h` | 46px | **100px** (2.17×) |
| Arrow glyph size | `--pad-glyph` | 24px | **48px** (2×) |
| Up/down separation | `--pad-gap` | 0 | **20px** (× each side of the label) |
| Inward margin from L/R edges | `--pad-side-inset` | ~4px | **30px** |
| Lift from bottom edge | `--pad-bottom` | 6px | **16px** |

Hit area grew ~4.8× (132×100 vs 60×46) — well past the ≥44px floor, as befits a primary control.

### Placement (≈390px portrait)

```text
┌────────────────────────────────────────────┐
│ 0:42  L3  pos +1  spread +$0.18         ?   │  HUD (top, untouched)
│                                              │
│            price canvas / quote lines        │
│                                              │
│     ▲                              ▲         │
│    ASK                            BID        │  ← inset 30px from edges,
│     ▼                              ▼         │     16px above the bottom
└────────────────────────────────────────────┘
```

- Still **bottom-left = ASK, bottom-right = BID** (two-handed thumb reach, mirrors W/S · P/L).
- **Clear of the price labels:** the canvas draws the right-edge price axis in the rightmost ~52px; with a 30px inset the BID arrow glyph is centered ~96px from the right edge, ~44px clear of the label column.
- **Anti-mis-hit:** the two button boxes are separated by the 20px gap plus a dead label strip (~53px of non-button space between the ▲ and ▼ hit areas). The label and the gaps are pass-through (only `.pad-btn` captures pointers now), so dragging the quote lines still works everywhere except the two arrow boxes.

Everything else is identical: borderless near-white (`--v`) arrows, no fill/box, `opacity 0.5 + scale 0.85` press flick, and the same `nudge()` → `applyQuotes` (D11 injection) path with hold-repeat driven by the `keys.ts` cadence constants — none of that logic was touched.

## Verification

- `npm run build` ✓ · vitest 25/25 ✓ · pytest 236/236 ✓ · eslint clean ✓ · self-review (geometry above) ✓.
- Production deployed; **deployed CSS hash matches the local build** (`index-Cj0hkAo4.css`) and contains the new vars (`--pad-btn-w: 132px`, etc.); `/` returns 200.

## Deferred / notes

- The enlarged invisible hit areas extend further up into the canvas, so the lower-corner regions are now larger dead zones for line-dragging (the buttons are the intended primary touch control there; the canvas centre stays drag-friendly). One-line var tweak if playtest wants them smaller.
- The BID button's *invisible* right edge still overlaps the price-label column by ~22px; the *visible* arrow is clear. Bump `--pad-side-inset` if a stray tap on the rightmost label is reported.
- Touch feel (size, reach, hold cadence) is for the human playtest — no headless browser is installed here to emulate touch, so this was verified by build + self-review only.
