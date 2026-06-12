/**
 * The 60-second live round (DESIGN.md §7.3): scrolling price canvas, fills
 * as side-colored flashes, bid/ask as touch-draggable lines. Censored feed:
 * no V, no declines, no trader types, no AS/IC — spread captured is the
 * only live PnL component (anything else would leak the hidden V, §1.4).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { FinishedRound, LiveRound } from "../game/live";
import { clockMmSs, COLORS, halfTicksToUsd, priceToUsd } from "./format";

const VIEW_SPAN_TICKS = 90; // vertical price window
const VIEW_WINDOW_US = 12_000_000; // trailing 12 s
const GRAB_PX = 36; // fat hit target for thumbs

interface Hud {
  secsLeft: number;
  position: number;
  scHalf: number;
  fills: number;
}

export function LiveScreen({ round, onDone }: { round: LiveRound; onDone: (f: FinishedRound) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState<"arm" | "run">("arm");
  const [hud, setHud] = useState<Hud>({ secsLeft: 60, position: 0, scHalf: 0, fills: 0 });
  const [quotes, setQuotes] = useState<[number, number]>([round.bid, round.ask]);

  const t0Ref = useRef(0);
  const centerRef = useRef(round.params.v0);
  const dragRef = useRef<"bid" | "ask" | null>(null);
  const doneRef = useRef(false);
  const phaseRef = useRef<"arm" | "run">("arm");
  phaseRef.current = phase;

  const gameT = useCallback((): number => {
    if (phaseRef.current !== "run") return 0;
    return Math.min(
      Math.floor((performance.now() - t0Ref.current) * 1000),
      round.params.round_us,
    );
  }, [round]);

  // ---- drawing -------------------------------------------------------------

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

    const now = gameT();
    // Smoothly track the quote mid.
    const mid = (round.bid + round.ask) / 2;
    centerRef.current += (mid - centerRef.current) * 0.08;
    const top = centerRef.current + VIEW_SPAN_TICKS / 2;
    const yOf = (price: number) => ((top - price) / VIEW_SPAN_TICKS) * h;
    const xOf = (t: number) => w - ((now - t) / VIEW_WINDOW_US) * w;

    // grid
    ctx.font = "10px ui-monospace, Menlo, monospace";
    ctx.fillStyle = COLORS.dim;
    ctx.strokeStyle = COLORS.rule;
    ctx.lineWidth = 1;
    const gridStep = 10;
    const firstLine = Math.ceil((top - VIEW_SPAN_TICKS) / gridStep) * gridStep;
    for (let p = firstLine; p <= top; p += gridStep) {
      const y = Math.round(yOf(p)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.globalAlpha = 0.35;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(priceToUsd(p), w - 52, y - 3);
    }

    // fills: side-colored dots fading over 3 s (censored: side only, never trader)
    for (let i = round.fills.length - 1; i >= 0; i--) {
      const f = round.fills[i];
      if (now - f.t_us > VIEW_WINDOW_US) break;
      const age = (now - f.t_us) / 3_000_000;
      const x = xOf(f.t_us);
      const y = yOf(f.price);
      ctx.globalAlpha = Math.max(0.25, 1 - age * 0.6);
      ctx.fillStyle = f.side === "buy" ? COLORS.buy : COLORS.sell;
      ctx.beginPath();
      ctx.arc(x, y, age < 0.15 ? 7 : 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // own quotes: draggable lines with handles
    for (const [price, color, label] of [
      [round.ask, COLORS.ask, "ASK"],
      [round.bid, COLORS.bid, "BID"],
    ] as const) {
      const y = Math.round(yOf(price)) + 0.5;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.fillRect(0, y - 9, 78, 18);
      ctx.fillStyle = COLORS.bg;
      ctx.font = "bold 11px ui-monospace, Menlo, monospace";
      ctx.fillText(`${label} ${priceToUsd(price)}`, 4, y + 4);
    }
  }, [round, gameT]);

  // ---- main loop -----------------------------------------------------------

  useEffect(() => {
    let raf = 0;
    const loop = () => {
      if (phaseRef.current === "run" && !doneRef.current) {
        const now = gameT();
        round.advanceTo(now);
        const next: Hud = {
          secsLeft: Math.ceil((round.params.round_us - now) / 1_000_000),
          position: round.position,
          scHalf: round.scLiveHalf(),
          fills: round.fills.length,
        };
        setHud((prev) =>
          prev.secsLeft === next.secsLeft &&
          prev.position === next.position &&
          prev.scHalf === next.scHalf &&
          prev.fills === next.fills
            ? prev
            : next,
        );
        if (now >= round.params.round_us) {
          doneRef.current = true;
          onDone(round.finish());
          return;
        }
      }
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [round, draw, gameT, onDone]);

  // ---- drag handling -------------------------------------------------------

  const priceAtY = (y: number, h: number): number => {
    const top = centerRef.current + VIEW_SPAN_TICKS / 2;
    return Math.round(top - (y / h) * VIEW_SPAN_TICKS);
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const h = rect.height;
    const top = centerRef.current + VIEW_SPAN_TICKS / 2;
    const yBid = ((top - round.bid) / VIEW_SPAN_TICKS) * h;
    const yAsk = ((top - round.ask) / VIEW_SPAN_TICKS) * h;
    const dBid = Math.abs(y - yBid);
    const dAsk = Math.abs(y - yAsk);
    if (Math.min(dBid, dAsk) > GRAB_PX) return;
    dragRef.current = dAsk <= dBid ? "ask" : "bid";
    canvas.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const which = dragRef.current;
    const canvas = canvasRef.current;
    if (!which || !canvas) return;
    const rect = canvas.getBoundingClientRect();
    const price = priceAtY(e.clientY - rect.top, rect.height);
    let { bid, ask } = round;
    if (which === "bid") bid = Math.min(price, ask - 1);
    else ask = Math.max(price, bid + 1);
    if (phaseRef.current === "arm") {
      round.bid = bid;
      round.ask = ask;
    } else {
      round.setQuotes(bid, ask, gameT());
    }
    setQuotes([round.bid, round.ask]);
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const start = () => {
    round.start();
    t0Ref.current = performance.now();
    setPhase("run");
  };

  const [bid, ask] = quotes;
  return (
    <div className="screen live">
      <div className="hud">
        <span className="hud-item hud-clock">{clockMmSs(hud.secsLeft * 1_000_000)}</span>
        <span className="hud-item">L{round.doc.level}</span>
        <span className="hud-item">
          pos <b>{hud.position > 0 ? `+${hud.position}` : hud.position}</b>
        </span>
        <span className="hud-item">
          spread captured <b className={hud.scHalf >= 0 ? "pos" : "neg"}>{halfTicksToUsd(hud.scHalf)}</b>
        </span>
        <span className="hud-item dim" title="Adverse selection and inventory cost depend on the hidden fair value — revealed at close (§1.4).">
          AS / IC revealed at close
        </span>
      </div>
      <div className="canvas-wrap">
        <canvas
          ref={canvasRef}
          className="price-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
        {phase === "arm" && (
          <div className="arm-overlay">
            <p>
              Fair value opens at <b>{priceToUsd(round.params.v0)}</b> — public knowledge, for the
              last time. Drag your <span style={{ color: COLORS.bid }}>BID</span> and{" "}
              <span style={{ color: COLORS.ask }}>ASK</span>, then start the clock.
            </p>
            <p className="dim">
              quoting {priceToUsd(bid)} / {priceToUsd(ask)} — spread {((ask - bid) / 100).toFixed(2)}
            </p>
            <button className="btn primary big" onClick={start}>
              START — 60s
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
