"""Render docs/replay.gif — a replay-screen-style animation of a real L4
round (Bot 1 as the dealer on a pool stream), drawn with matplotlib in the
game's grey-terminal palette. Stylized render of the replay's content (V
reveal, quote steps, fills, pick-off rings, declines); swap in a true
screen recording any time.

Run from the repo root:
    /opt/anaconda3/bin/python3 docs/render_replay_gif.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim"))

from picked_off.bots.base import run_bot  # noqa: E402
from picked_off.bots.bot1 import Bot1  # noqa: E402
from picked_off.events import parse_stream  # noqa: E402
from picked_off.params import SimParams  # noqa: E402
from picked_off.scoring import value_at  # noqa: E402

STREAM = ROOT / "web" / "public" / "streams" / "L4-901009.json"
OUT = ROOT / "docs" / "replay.gif"

BG, PANEL, RULE, TEXT, DIM = "#1b1d1f", "#232527", "#3a3d40", "#c9ccce", "#7e8387"
BUY, SELL, PICK, V_COL, BID, ASK = "#6fc2d8", "#d8b46f", "#d9534f", "#e8e9ea", "#8fa3b8", "#b8a08f"

N_FRAMES, FPS = 72, 9


def step_xy(points, t_end, t0_val):
    """Build step-line arrays from [(t_us, value)] up to t_end."""
    xs, ys = [0.0], [t0_val]
    for t, v in points:
        if t > t_end:
            break
        xs += [t / 1e6, t / 1e6]
        ys += [ys[-1], v]
    xs.append(t_end / 1e6)
    ys.append(ys[-1])
    return xs, ys


def main() -> None:
    doc = json.loads(STREAM.read_text())
    params = SimParams.from_meta(doc["params"])
    exo = parse_stream(doc["event_stream"], params.round_us, require_opening_quote=False)
    r = run_bot(params, exo, Bot1())

    jumps = [(j.t_us, None) for j in r.jumps]
    v_steps = []
    v = params.v0
    for j in r.jumps:
        v += j.size
        v_steps.append((j.t_us, v))
    bid_steps = [(q.t_us, q.bid) for q in r.quotes]
    ask_steps = [(q.t_us, q.ask) for q in r.quotes]

    lo = min([params.v0, *[v for _, v in v_steps], *[f.price for f in r.fills]]) - 6
    hi = max([params.v0, *[v for _, v in v_steps], *[f.price for f in r.fills]]) + 6

    frames = []
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=100)
    for k in range(N_FRAMES):
        t_end = int(params.round_us * (k + 1) / N_FRAMES)
        ax.clear()
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(PANEL)
        ax.set_xlim(0, params.round_us / 1e6)
        ax.set_ylim(lo, hi)
        ax.tick_params(colors=DIM, labelsize=7)
        for s in ax.spines.values():
            s.set_color(RULE)
        ax.grid(color=RULE, alpha=0.3, linewidth=0.5)
        ax.set_yticks(np.arange(np.ceil(lo / 10) * 10, hi, 10))
        ax.set_yticklabels([f"${y / 100:.2f}" for y in ax.get_yticks()])
        ax.set_xticks([0, 15, 30, 45, 60])
        ax.set_xticklabels(["0s", "15s", "30s", "45s", "60s"])

        xs, ys = step_xy(ask_steps, t_end, ask_steps[0][1])
        ax.plot(xs, ys, color=ASK, lw=0.9, alpha=0.9)
        xs, ys = step_xy(bid_steps, t_end, bid_steps[0][1])
        ax.plot(xs, ys, color=BID, lw=0.9, alpha=0.9)
        xs, ys = step_xy(v_steps, t_end, params.v0)
        ax.plot(xs, ys, color=V_COL, lw=1.6)

        for d in r.declines:
            if d.t_us > t_end:
                continue
            if d.trader == "informed":
                ax.plot(d.t_us / 1e6, value_at(params.v0, r.jumps, d.t_us), marker="s",
                        ms=3.5, mfc="none", mec=PICK, mew=0.9, alpha=0.8)
            else:
                ax.plot(d.t_us / 1e6, value_at(params.v0, r.jumps, d.t_us), marker="x",
                        ms=2.5, color=DIM, alpha=0.4)
        for f in r.fills:
            if f.t_us > t_end:
                continue
            c = BUY if f.side == "buy" else SELL
            ax.plot(f.t_us / 1e6, f.price, "o", ms=3.5, color=c)
            if f.trader == "informed":
                ax.plot(f.t_us / 1e6, f.price, "o", ms=7, mfc="none", mec=PICK, mew=1.4)

        ax.axvline(t_end / 1e6, color=TEXT, lw=0.7, alpha=0.5)
        ax.set_title("PICKED OFF — replay (L4, Bayesian dealer) · white: hidden value · red rings: pick-offs",
                     color=DIM, fontsize=8, loc="left", pad=6)
        fig.tight_layout()
        fig.canvas.draw()
        frames.append(Image.frombuffer("RGBA", fig.canvas.get_width_height(),
                                       fig.canvas.buffer_rgba()).convert("P", palette=Image.ADAPTIVE))
    plt.close(fig)

    frames[0].save(OUT, save_all=True, append_images=frames[1:] + [frames[-1]] * (FPS * 2),
                   duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {N_FRAMES} frames)")


if __name__ == "__main__":
    main()
