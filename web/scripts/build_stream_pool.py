"""Pre-generate the live-round stream pool (build step ④, DESIGN.md §7.3 / D12).

Invokes the FROZEN Python generator (sim/ is not modified) to produce
certified exogenous streams — jumps + arrivals only, no quote events (the
player provides quotes live) — at the final §1.5 level table: 40 rounds per
level x 5 levels, written to web/public/streams/ as static assets.

Each stream is hygiene-certified and V>0-certified by generate_stream itself
(CertificationError -> deterministic seed re-roll, mirroring the gate
runner). The browser picks uniformly from the pool at round start (UI-level
randomness only; engines stay RNG-free per §0 rule 3) and records the
stream_id for exact replay.

Run from the repo root:
    /opt/anaconda3/bin/python3 web/scripts/build_stream_pool.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sim"))

from picked_off.events import event_to_json  # noqa: E402
from picked_off.generator import SEED_RETRY_STEP, CertificationError, generate_stream  # noqa: E402
from picked_off.params import LEVEL_ALPHAS, SimParams  # noqa: E402

OUT = ROOT / "web" / "public" / "streams"
PER_LEVEL = 40
BASE_SEED = 500_000


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index: dict[str, list[str]] = {}
    total_bytes = 0
    for level in sorted(LEVEL_ALPHAS):
        params = SimParams.for_level(level)
        ids = []
        for i in range(PER_LEVEL):
            seed = BASE_SEED + level * 100_000 + i * 1_009
            for _ in range(100):
                try:
                    events = generate_stream(params, seed, None)
                    break
                except CertificationError:
                    seed += SEED_RETRY_STEP
            else:
                raise SystemExit(f"no valid stream near seed for level {level} round {i}")
            stream_id = f"L{level}-{seed}"
            doc = {
                "stream_id": stream_id,
                "level": level,
                "seed": seed,
                "params": params.to_meta(),
                "event_stream": [event_to_json(ev) for ev in events],
            }
            path = OUT / f"{stream_id}.json"
            path.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
            total_bytes += path.stat().st_size
            ids.append(stream_id)
        index[str(level)] = ids
        print(f"level {level} (alpha={params.alpha}): {len(ids)} streams")
    (OUT / "index.json").write_text(json.dumps(index) + "\n")
    print(f"pool: {sum(len(v) for v in index.values())} streams, {total_bytes / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
