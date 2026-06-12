/**
 * The replay screen (DESIGN.md §1.4, §7.3) — the reveal. True V path over
 * the player's quote history; every fill annotated; every decline shown
 * (informed pass vs noise balk); pick-offs ringed red; per-fill markouts.
 * Scrubable and auto-playing.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { FinishedRound } from "../game/live";
import { downloadSession } from "../game/session";
import { COLORS, halfTicksToUsd, priceToUsd, ticksToUsd } from "./format";

function quotesAt(round: FinishedRound, tUs: number): [number, number] {
  let bid = round.result.quotes[0].bid;
  let ask = round.result.quotes[0].ask;
  for (const q of round.result.quotes) {
    if (q.t_us > tUs) break;
    bid = q.bid;
    ask = q.ask;
  }
  return [bid, ask];
}

function vAt(round: FinishedRound, tUs: number): number {
  let v = round.result.params.v0;
  for (const j of round.result.jumps) {
    if (j.t_us > tUs) break;
    v += j.size;
  }
  return v;
}

export function ReplayScreen({
  round,
  onBack,
  onMenu,
  onHome,
}: {
  round: FinishedRound;
  onBack: () => void;
  onMenu: () => void;
  onHome: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const T = round.result.params.round_us;
  const [scrub, setScrub] = useState(T);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const [selected, setSelected] = useState<number | null>(null);
  // Decline markers clutter badly at L4/L5 (~100+ walk-aways): default to
  // pick-offs-only there (REPORT3 rough edge (a)).
  const [markers, setMarkers] = useState<"pickoffs" | "all">(round.level >= 4 ? "pickoffs" : "all");
  const scrubRef = useRef(scrub);
  scrubRef.current = scrub;

  // price range over everything revealed
  const rangeRef = useRef<[number, number] | null>(null);
  if (!rangeRef.current) {
    let lo = Infinity;
    let hi = -Infinity;
    const widen = (p: number) => {
      lo = Math.min(lo, p);
      hi = Math.max(hi, p);
    };
    let v = round.result.params.v0;
    widen(v);
    for (const j of round.result.jumps) widen((v += j.size));
    for (const q of round.result.quotes) {
      widen(q.bid);
      widen(q.ask);
    }
    for (const f of round.result.fills) widen(f.price);
    rangeRef.current = [lo - 6, hi + 6];
  }

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const [lo, hi] = rangeRef.current!;
    const xOf = (t: number) => (t / T) * w;
    const yOf = (p: number) => ((hi - p) / (hi - lo)) * h;
    const t = scrubRef.current;
    const r = round.result;

    // grid
    ctx.font = "10px ui-monospace, Menlo, monospace";
    const step = Math.max(5, Math.round((hi - lo) / 8 / 5) * 5);
    ctx.lineWidth = 1;
    for (let p = Math.ceil(lo / step) * step; p <= hi; p += step) {
      const y = Math.round(yOf(p)) + 0.5;
      ctx.strokeStyle = COLORS.rule;
      ctx.globalAlpha = 0.3;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = COLORS.dim;
      ctx.fillText(priceToUsd(p), w - 50, y - 3);
    }

    // quote history (step lines), drawn up to scrub time
    const drawQuoteStep = (pick: (q: { bid: number; ask: number }) => number, color: string) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      let prevPrice: number | null = null;
      let prevT = 0;
      for (const q of r.quotes) {
        if (q.t_us > t) break;
        const price = pick(q);
        if (prevPrice !== null) {
          ctx.lineTo(xOf(q.t_us), yOf(prevPrice));
        } else {
          ctx.moveTo(xOf(q.t_us), yOf(price));
        }
        ctx.lineTo(xOf(q.t_us), yOf(price));
        prevPrice = price;
        prevT = q.t_us;
      }
      if (prevPrice !== null) ctx.lineTo(xOf(Math.min(t, T)), yOf(prevPrice));
      ctx.stroke();
      ctx.globalAlpha = 1;
      void prevT;
    };
    drawQuoteStep((q) => q.ask, COLORS.ask);
    drawQuoteStep((q) => q.bid, COLORS.bid);

    // the true V path — the reveal
    ctx.strokeStyle = COLORS.v;
    ctx.lineWidth = 1.75;
    ctx.beginPath();
    let v = r.params.v0;
    ctx.moveTo(0, yOf(v));
    for (const j of r.jumps) {
      if (j.t_us > t) break;
      ctx.lineTo(xOf(j.t_us), yOf(v));
      v += j.size;
      ctx.lineTo(xOf(j.t_us), yOf(v));
    }
    ctx.lineTo(xOf(Math.min(t, T)), yOf(v));
    ctx.stroke();

    // declines (§1.4 reveal) — hidden in pick-offs-only marker mode
    for (const d of markers === "all" ? r.declines : []) {
      if (d.t_us > t) continue;
      const x = xOf(d.t_us);
      if (d.trader === "informed") {
        // informed pass: V was inside the quotes — hollow red diamond at V
        const y = yOf(vAt(round, d.t_us));
        ctx.strokeStyle = COLORS.pickoff;
        ctx.globalAlpha = 0.8;
        ctx.strokeRect(x - 3, y - 3, 6, 6);
        ctx.globalAlpha = 1;
      } else {
        // noise balk: grey x at the quote it refused
        const [b, a] = quotesAt(round, d.t_us);
        const y = yOf(d.side_intent === "buy" ? a : b);
        ctx.strokeStyle = COLORS.dim;
        ctx.globalAlpha = 0.7;
        ctx.beginPath();
        ctx.moveTo(x - 3, y - 3);
        ctx.lineTo(x + 3, y + 3);
        ctx.moveTo(x - 3, y + 3);
        ctx.lineTo(x + 3, y - 3);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }

    // fills — side-colored; pick-offs (informed fills) ringed red
    r.fills.forEach((f, i) => {
      if (f.t_us > t) return;
      const x = xOf(f.t_us);
      const y = yOf(f.price);
      ctx.fillStyle = f.side === "buy" ? COLORS.buy : COLORS.sell;
      ctx.beginPath();
      ctx.arc(x, y, selected === i ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();
      if (f.trader === "informed") {
        ctx.strokeStyle = COLORS.pickoff;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, selected === i ? 9 : 7, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (selected === i) {
        ctx.strokeStyle = COLORS.text;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.globalAlpha = 0.4;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    });

    // scrub cursor
    const cx = Math.round(xOf(Math.min(t, T))) + 0.5;
    ctx.strokeStyle = COLORS.text;
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }, [round, T, selected, markers]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      if (playing) {
        const dt = (now - last) * 1000 * speed;
        const next = Math.min(scrubRef.current + dt, T);
        setScrub(next);
        if (next >= T) setPlaying(false);
      }
      last = now;
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, T, draw]);

  const onClickCanvas = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const [lo, hi] = rangeRef.current!;
    let best: number | null = null;
    let bestD = 24;
    round.result.fills.forEach((f, i) => {
      if (f.t_us > scrubRef.current) return;
      const fx = (f.t_us / T) * rect.width;
      const fy = ((hi - f.price) / (hi - lo)) * rect.height;
      const d = Math.hypot(fx - x, fy - y);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setSelected(best);
  };

  const sel = selected !== null ? round.result.fills[selected] : null;
  const selScore = selected !== null ? round.fillScores[selected] : null;
  const pickoffs = round.result.fills.filter((f) => f.trader === "informed").length;
  const passes = round.result.declines.filter((d) => d.trader === "informed").length;
  const balks = round.result.declines.length - passes;

  return (
    <div className="screen replay">
      <div className="hud">
        <span className="hud-item">REPLAY — L{round.level}</span>
        <span className="hud-item">{round.streamId}</span>
        <span className="hud-item">
          <b className="neg">{pickoffs}</b> pick-offs
        </span>
        <span className="hud-item">
          <b>{passes}</b> informed passed
        </span>
        <span className="hud-item">
          <b>{balks}</b> balked at the spread
        </span>
      </div>
      <div className="canvas-wrap">
        <canvas ref={canvasRef} className="price-canvas" onClick={onClickCanvas} />
      </div>
      <div className="replay-controls">
        <button className="btn" onClick={() => setPlaying((p) => (scrub >= T ? (setScrub(0), true) : !p))}>
          {playing ? "Pause" : "Play"}
        </button>
        <button className="btn" onClick={() => setSpeed((s) => (s === 4 ? 1 : 4))}>{speed}×</button>
        <button
          className="btn"
          onClick={() => setMarkers((m) => (m === "all" ? "pickoffs" : "all"))}
          title="Decline-marker density"
        >
          {markers === "all" ? "all markers" : "pick-offs only"}
        </button>
        <input
          className="scrub"
          type="range"
          min={0}
          max={T}
          step={100_000}
          value={scrub}
          onChange={(e) => {
            setPlaying(false);
            setScrub(Number(e.target.value));
          }}
        />
        <span className="dim">{(scrub / 1_000_000).toFixed(1)}s</span>
      </div>
      <div className="replay-detail">
        {sel && selScore ? (
          <p>
            <b className={sel.trader === "informed" ? "neg" : ""}>
              {sel.trader === "informed" ? "PICKED OFF" : "noise"}
            </b>{" "}
            · customer {sel.side === "buy" ? "bought" : "sold"} at {priceToUsd(sel.price)} while V ={" "}
            {priceToUsd(sel.v_at_fill)} · spread {halfTicksToUsd(selScore.sc_half)} · adverse{" "}
            {halfTicksToUsd(selScore.as_half)} · inventory {halfTicksToUsd(selScore.ic_half)} ·
            markout +1s {ticksToUsd(selScore.markout_1s)} / +5s {ticksToUsd(selScore.markout_5s)}
          </p>
        ) : (
          <p className="dim">
            White line: the fair value you never saw. Red rings: fills that picked you off.
            {markers === "all"
              ? " Red squares: informed traders who looked and declined — V was inside. Grey ×: noise that balked at your spread."
              : " Decline markers hidden — switch to “all markers” to see who walked away."}{" "}
            Tap a fill for its anatomy.
          </p>
        )}
      </div>
      <div className="btn-row">
        <button className="btn" onClick={onBack}>
          Back to score
        </button>
        <button className="btn" onClick={onMenu}>
          Levels
        </button>
        <button className="btn" onClick={onHome}>
          Home
        </button>
        <button className="btn" onClick={() => downloadSession(round)}>
          Download my session
        </button>
      </div>
    </div>
  );
}
