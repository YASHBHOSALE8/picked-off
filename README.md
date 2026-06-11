# Picked Off

A browser market-making game built on the Glosten–Milgrom adverse-selection model. You are the sole dealer: drag your bid and ask against a hidden fair value while order flow — part noise, part traders who know exactly what the asset is worth — decides whether to hit you or walk away silently. Your score is decomposed exactly into spread captured, adverse selection, and inventory cost, and the post-round replay reveals every trader who picked you off or balked at your spread. A Python simulator is the source of truth, a React/TypeScript front end mirrors it bit-for-bit through shared golden test vectors, and research bots (including a Bayesian dealer that reads the silences) establish what optimal play looks like.

**Status: building** — step ① of ⑤ (spec + scaffold). See [DESIGN.md](DESIGN.md) for the full specification.

![Replay GIF placeholder — coming in step ⑤](docs/replay.gif)

## Layout

- [`DESIGN.md`](DESIGN.md) — the spec; source of truth
- [`sim/`](sim/) — Python simulator (canonical engine, bots, golden-vector generator)
- [`web/`](web/) — React + TS + Vite game client
- [`vectors/`](vectors/) — golden test vectors consumed by both engines
- [`notebooks/`](notebooks/) — parameter-search and analysis notebooks
- [`writeup/`](writeup/) — research writeup

## License

MIT — see [LICENSE](LICENSE).
