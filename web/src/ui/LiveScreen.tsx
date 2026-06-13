/**
 * The live round (DESIGN.md §7.3): scrolling price canvas, side-colored fill
 * flashes, bid/ask draggable by touch or nudged by keyboard (keys.ts; same
 * D11 injection path). Censored feed: no V, no declines, no trader types,
 * no AS/IC (§1.4) — spread captured is the only live PnL component.
 *
 * Pausing is depth-counted and shared by tutorial cards and the app-level
 * freeze (the leave-round confirm dialog): while paused the game clock,
 * input, and event processing all hold.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { FinishedRound, LiveRound } from "../game/live";
import { clockMmSs, COLORS, halfTicksToUsd, priceToUsd } from "./format";
import {
  hasFinePointer,
  KEY_HINTS,
  KEY_HOLD_DELAY_MS,
  KEY_HOLD_REPEAT_MS,
  KEY_STEP,
  KEY_STEP_SHIFT,
  KEYMAP,
} from "./keys";
import { CARDS, NOPICKOFF_FALLBACK_T_US, TUTORIAL_ARM_TEXT, type TutorialCard } from "./tutorial";

const VIEW_SPAN_TICKS = 90;
const VIEW_WINDOW_US = 12_000_000;
const GRAB_PX = 36;

interface Hud {
  secsLeft: number;
  position: number;
  scHalf: number;
  fills: number;
}

type Dir = "askUp" | "askDown" | "bidUp" | "bidDown";

/** Borderless white-arrow nudge button (touch). Tap = one nudge; hold = repeat
 * (driven by the parent's startHold/endHold). Pointer-captured so a finger
 * that slides off still releases the hold on lift. */
function PadButton({
  dir,
  glyph,
  label,
  onStart,
  onEnd,
}: {
  dir: Dir;
  glyph: string;
  label: string;
  onStart: (d: Dir) => void;
  onEnd: () => void;
}) {
  return (
    <button
      className="pad-btn"
      aria-label={label}
      onPointerDown={(e) => {
        e.preventDefault();
        e.currentTarget.setPointerCapture?.(e.pointerId);
        onStart(dir);
      }}
      onPointerUp={onEnd}
      onPointerCancel={onEnd}
      onContextMenu={(e) => e.preventDefault()}
    >
      {glyph}
    </button>
  );
}

const HELP_LINES = [
  ["The lines", "Your quotes. You BUY at the bid (lower), SELL at the ask (upper). Drag, or W/S · P/L."],
  ["The dots", "Fills. Cyan: someone bought at your ask. Amber: someone sold at your bid."],
  ["The silence", "No fills means no customers — or customers who refused your price. You can't tell which."],
  ["pos", "Your inventory. Marked at the TRUE value at the close — holding is risk."],
  ["α (level)", "The share of arrivals who know the true value exactly. They only trade when you're wrong."],
] as const;

export function LiveScreen({
  round,
  onDone,
  tutorial = false,
  onSkip,
  onExit,
  frozen = false,
}: {
  round: LiveRound;
  onDone: (f: FinishedRound) => void;
  tutorial?: boolean;
  onSkip?: () => void;
  onExit?: () => void;
  frozen?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState<"arm" | "run">("arm");
  const [hud, setHud] = useState<Hud>({ secsLeft: 60, position: 0, scHalf: 0, fills: 0 });
  const [quotes, setQuotesState] = useState<[number, number]>([round.bid, round.ask]);
  const [helpOpen, setHelpOpen] = useState(false);
  const [card, setCard] = useState<TutorialCard | null>(null);

  const t0Ref = useRef(0);
  const pauseDepthRef = useRef(0);
  const pauseStartRef = useRef(0);
  const pausedAccumRef = useRef(0);
  const cardRef = useRef<TutorialCard | null>(null);
  const shownRef = useRef<Set<string>>(new Set());
  const lastFillCountRef = useRef(0);
  const centerRef = useRef(round.params.v0);
  const dragRef = useRef<"bid" | "ask" | null>(null);
  const doneRef = useRef(false);
  const phaseRef = useRef<"arm" | "run">("arm");
  phaseRef.current = phase;
  const keyHints = useRef(hasFinePointer()).current;
  const touchControls = !keyHints; // coarse pointer: show on-screen pads instead

  const pausePush = useCallback(() => {
    if (pauseDepthRef.current === 0) pauseStartRef.current = performance.now();
    pauseDepthRef.current += 1;
  }, []);

  const pausePop = useCallback(() => {
    pauseDepthRef.current = Math.max(0, pauseDepthRef.current - 1);
    if (pauseDepthRef.current === 0) {
      pausedAccumRef.current += performance.now() - pauseStartRef.current;
    }
  }, []);

  // App-level freeze (leave-confirm dialog) participates in the same pause.
  const frozenRef = useRef(false);
  useEffect(() => {
    if (frozen && !frozenRef.current) {
      frozenRef.current = true;
      pausePush();
    } else if (!frozen && frozenRef.current) {
      frozenRef.current = false;
      pausePop();
    }
  }, [frozen, pausePush, pausePop]);

  const gameT = useCallback((): number => {
    if (phaseRef.current !== "run") return 0;
    const now = pauseDepthRef.current > 0 ? pauseStartRef.current : performance.now();
    return Math.min(Math.floor((now - t0Ref.current - pausedAccumRef.current) * 1000), round.params.round_us);
  }, [round]);

  const showCard = useCallback(
    (c: TutorialCard) => {
      if (shownRef.current.has(c.id)) return;
      shownRef.current.add(c.id);
      pausePush();
      cardRef.current = c;
      setCard(c);
    },
    [pausePush],
  );

  const dismissCard = useCallback(() => {
    const c = cardRef.current;
    cardRef.current = null;
    setCard(null);
    pausePop();
    if (c?.id === "end" && !doneRef.current) {
      doneRef.current = true;
      onDone(round.finish());
    }
  }, [onDone, round, pausePop]);

  // ---- quote mutation (shared by drag + keyboard; same engine path) -------

  const applyQuotes = useCallback(
    (bid: number, ask: number) => {
      if (ask < bid + 1) return;
      if (phaseRef.current === "arm") {
        round.bid = bid;
        round.ask = ask;
      } else {
        round.setQuotes(bid, ask, gameT());
      }
      setQuotesState([round.bid, round.ask]);
    },
    [round, gameT],
  );

  // ---- the one quote-mutation path: keyboard AND touch pads both call
  //      nudge -> applyQuotes -> the same D11 injection as dragging ----------

  const nudge = useCallback(
    (which: Dir, step: number) => {
      if (pauseDepthRef.current > 0) return;
      let { bid, ask } = round;
      if (which === "askUp") ask += step;
      else if (which === "askDown") ask = Math.max(ask - step, bid + 1);
      else if (which === "bidUp") bid = Math.min(bid + step, ask - 1);
      else bid -= step; // bidDown
      applyQuotes(bid, ask);
    },
    [round, applyQuotes],
  );

  // keyboard (desktop): hold = native OS key-repeat, no JS timer needed
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      let which: Dir | null = null;
      if (k === KEYMAP.askUp) which = "askUp";
      else if (k === KEYMAP.askDown) which = "askDown";
      else if (k === KEYMAP.bidUp) which = "bidUp";
      else if (k === KEYMAP.bidDown) which = "bidDown";
      if (!which) return;
      e.preventDefault();
      nudge(which, e.shiftKey ? KEY_STEP_SHIFT : KEY_STEP);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nudge]);

  // touch pads: tap = one nudge; press-and-hold repeats at the keys.ts cadence
  const holdRef = useRef<{ t: number; i: number } | null>(null);
  const endHold = useCallback(() => {
    const h = holdRef.current;
    if (!h) return;
    if (h.t) window.clearTimeout(h.t);
    if (h.i) window.clearInterval(h.i);
    holdRef.current = null;
  }, []);
  const startHold = useCallback(
    (which: Dir) => {
      endHold();
      nudge(which, KEY_STEP); // immediate first step
      const t = window.setTimeout(() => {
        const i = window.setInterval(() => nudge(which, KEY_STEP), KEY_HOLD_REPEAT_MS);
        holdRef.current = { t: 0, i };
      }, KEY_HOLD_DELAY_MS);
      holdRef.current = { t, i: 0 };
    },
    [nudge, endHold],
  );
  useEffect(() => endHold, [endHold]); // clear any live hold on unmount

  // Touch pads are shown only during the running clock (the arm overlay owns
  // the bottom strip pre-start). Clear a held button whenever they hide.
  const showPads = touchControls && phase === "run" && !card && !frozen;
  useEffect(() => {
    if (!showPads) endHold();
  }, [showPads, endHold]);

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
    const mid = (round.bid + round.ask) / 2;
    centerRef.current += (mid - centerRef.current) * 0.08;
    const top = centerRef.current + VIEW_SPAN_TICKS / 2;
    const yOf = (price: number) => ((top - price) / VIEW_SPAN_TICKS) * h;
    const xOf = (t: number) => w - ((now - t) / VIEW_WINDOW_US) * w;

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

    for (let i = round.fills.length - 1; i >= 0; i--) {
      const f = round.fills[i];
      if (now - f.t_us > VIEW_WINDOW_US) break;
      const age = (now - f.t_us) / 3_000_000;
      ctx.globalAlpha = Math.max(0.25, 1 - age * 0.6);
      ctx.fillStyle = f.side === "buy" ? COLORS.buy : COLORS.sell;
      ctx.beginPath();
      ctx.arc(xOf(f.t_us), yOf(f.price), age < 0.15 ? 7 : 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    for (const [price, color, label, hint] of [
      [round.ask, COLORS.ask, "ASK", KEY_HINTS.ask],
      [round.bid, COLORS.bid, "BID", KEY_HINTS.bid],
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
      if (keyHints) {
        ctx.fillStyle = COLORS.dim;
        ctx.font = "10px ui-monospace, Menlo, monospace";
        ctx.fillText(hint, 84, y + 4);
      }
    }
  }, [round, gameT, keyHints]);

  // ---- main loop -----------------------------------------------------------

  useEffect(() => {
    let raf = 0;
    const loop = () => {
      if (phaseRef.current === "run" && !doneRef.current && pauseDepthRef.current === 0) {
        const now = gameT();
        round.advanceTo(now);

        if (tutorial) {
          while (lastFillCountRef.current < round.fills.length && pauseDepthRef.current === 0) {
            const f = round.fills[lastFillCountRef.current];
            lastFillCountRef.current += 1;
            if (f.trader === "informed") {
              showCard(CARDS.pickoff);
              break;
            }
            if (!shownRef.current.has("firstfill")) {
              showCard(CARDS.firstfill);
              break;
            }
            if (lastFillCountRef.current === 2 && !shownRef.current.has("spread")) {
              showCard(CARDS.spread);
              break;
            }
          }
          if (
            pauseDepthRef.current === 0 &&
            now >= NOPICKOFF_FALLBACK_T_US &&
            !shownRef.current.has("pickoff") &&
            !shownRef.current.has("nopickoff")
          ) {
            showCard(CARDS.nopickoff);
          }
        }

        if (pauseDepthRef.current === 0) {
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
            if (tutorial && !shownRef.current.has("end")) {
              showCard(CARDS.end);
            } else if (!tutorial) {
              doneRef.current = true;
              onDone(round.finish());
              return;
            }
          }
        }
      }
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [round, draw, gameT, onDone, tutorial, showCard]);

  // ---- drag handling -------------------------------------------------------

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || pauseDepthRef.current > 0) return;
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
    if (!which || !canvas || pauseDepthRef.current > 0) return;
    const rect = canvas.getBoundingClientRect();
    const top = centerRef.current + VIEW_SPAN_TICKS / 2;
    const price = Math.round(top - ((e.clientY - rect.top) / rect.height) * VIEW_SPAN_TICKS);
    let { bid, ask } = round;
    if (which === "bid") bid = Math.min(price, ask - 1);
    else ask = Math.max(price, bid + 1);
    applyQuotes(bid, ask);
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const start = () => {
    round.start();
    t0Ref.current = performance.now();
    pausedAccumRef.current = 0;
    setPhase("run");
  };

  const [bid, ask] = quotes;
  return (
    <div className="screen live">
      <div className="hud">
        {onExit && (
          <button className="btn help-btn exit-btn" onClick={onExit} title="Leave the round">
            ←
          </button>
        )}
        <span className="hud-item hud-clock">{clockMmSs(hud.secsLeft * 1_000_000)}</span>
        <span className="hud-item">{tutorial ? "TUTORIAL" : `L${round.doc.level}`}</span>
        <span className="hud-item">
          pos <b>{hud.position > 0 ? `+${hud.position}` : hud.position}</b>
        </span>
        <span className="hud-item">
          spread captured <b className={hud.scHalf >= 0 ? "pos" : "neg"}>{halfTicksToUsd(hud.scHalf)}</b>
        </span>
        <span className="hud-item dim">AS / IC revealed at close</span>
        {keyHints && <span className="hud-item dim">{KEY_HINTS.modifier}</span>}
        <button
          className={`btn help-btn ${helpOpen ? "primary" : ""}`}
          onClick={() => setHelpOpen((o) => !o)}
          title="What's going on?"
        >
          ?
        </button>
        {tutorial && onSkip && (
          <button className="btn help-btn dim" onClick={onSkip}>
            skip
          </button>
        )}
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
        {helpOpen && (
          <div className="help-overlay" onClick={() => setHelpOpen(false)}>
            {HELP_LINES.map(([term, line]) => (
              <p key={term}>
                <b>{term}</b> — {line}
              </p>
            ))}
          </div>
        )}
        {phase === "arm" && (
          <div className="arm-overlay">
            {tutorial ? (
              <p>{TUTORIAL_ARM_TEXT}</p>
            ) : (
              <p>
                Fair value opens at <b>{priceToUsd(round.params.v0)}</b> — public knowledge, for the
                last time. Drag your <span style={{ color: COLORS.bid }}>BID</span> and{" "}
                <span style={{ color: COLORS.ask }}>ASK</span>
                {keyHints ? " (or W/S · P/L)" : ""}, then start the clock.
              </p>
            )}
            <p className="dim">
              quoting {priceToUsd(bid)} / {priceToUsd(ask)} — spread {((ask - bid) / 100).toFixed(2)}
            </p>
            <button className="btn primary big" onClick={start}>
              {tutorial ? "START PRACTICE — 30s" : "START — 60s"}
            </button>
          </div>
        )}
        {card && (
          <div className="tutorial-card">
            <h3 className={card.id === "pickoff" ? "neg" : ""}>{card.title}</h3>
            <p>{card.body}</p>
            <button className="btn primary" onClick={dismissCard}>
              {card.id === "end" ? "Finish" : "Got it"}
            </button>
          </div>
        )}
        {showPads && (
          <div className="quote-pads">
            {/* left = ASK, right = BID — mirrors the keyboard's W/S · P/L split */}
            <div className="quote-pad">
              <PadButton dir="askUp" glyph="▲" label="ask up" onStart={startHold} onEnd={endHold} />
              <span className="pad-label">ASK</span>
              <PadButton dir="askDown" glyph="▼" label="ask down" onStart={startHold} onEnd={endHold} />
            </div>
            <div className="quote-pad">
              <PadButton dir="bidUp" glyph="▲" label="bid up" onStart={startHold} onEnd={endHold} />
              <span className="pad-label">BID</span>
              <PadButton dir="bidDown" glyph="▼" label="bid down" onStart={startHold} onEnd={endHold} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
