/**
 * The normative event loop (DESIGN.md §3). Mirror of sim/picked_off/engine.py.
 * All price/time arithmetic in integer ticks/µs; no RNG anywhere (§0 rule 3).
 *
 * Two output channels (§3): the censored public feed is exactly fills +
 * quotes (what live play shows); the full log adds declines + jumps
 * (unlocked for replay only).
 */

import type { JumpEvent, QuoteEvent, StreamEvent } from "./events";
import type { SimParams } from "./params";

export class EngineError extends Error {}

/** f(h) = exp(-h/delta0) with h = (ask-bid)/2 ticks (DESIGN.md §1.3). */
export function noiseAcceptProb(bid: number, ask: number, delta0: number): number {
  return Math.exp(-(ask - bid) / (2.0 * delta0));
}

export interface Fill {
  t_us: number;
  /** Customer side: "buy" = customer buys at the ask (dealer sells). */
  side: "buy" | "sell";
  price: number;
  v_at_fill: number;
  trader: "informed" | "noise";
  bid: number; // dealer quotes standing at the fill (scoring §2.2)
  ask: number;
}

/** Dealer position change (§0): -1 on customer buy, +1 on customer sell. */
export function fillQ(f: Fill): number {
  return f.side === "buy" ? -1 : +1;
}

export interface Decline {
  t_us: number;
  trader: "informed" | "noise";
  side_intent: "buy" | "sell" | null;
  reason: "v_inside_quotes" | "balked_at_spread";
}

export interface RoundResult {
  params: SimParams;
  fills: Fill[];
  declines: Decline[];
  jumps: JumpEvent[];
  quotes: QuoteEvent[];
  v_terminal: number;
  cash: number;
  inventory: number;
}

function intOrDie(value: number, what: string, tUs: number): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new EngineError(`${what} must be an integer at t_us=${tUs}, got ${String(value)}`);
  }
  return value;
}

export class Engine {
  readonly params: SimParams;
  v: number;
  quotes: [number, number] | null = null;
  cash = 0;
  inventory = 0;
  private lastT = -1;
  private fills: Fill[] = [];
  private declines: Decline[] = [];
  private jumps: JumpEvent[] = [];
  private quoteLog: QuoteEvent[] = [];
  private finalized = false;

  constructor(params: SimParams) {
    this.params = params;
    this.v = params.v0;
  }

  apply(ev: StreamEvent): Fill | Decline | null {
    if (this.finalized) throw new EngineError("engine already finalized");
    intOrDie(ev.t_us, "t_us", ev.t_us);
    if (ev.t_us <= this.lastT) {
      throw new EngineError(
        `timestamps must be strictly increasing: ${ev.t_us} after ${this.lastT} (§0 rule 2)`,
      );
    }
    if (!(ev.t_us >= 0 && ev.t_us < this.params.round_us)) {
      throw new EngineError(`t_us=${ev.t_us} outside [0, ${this.params.round_us})`);
    }
    this.lastT = ev.t_us;

    if (ev.type === "quote") {
      const bid = intOrDie(ev.bid, "bid", ev.t_us);
      const ask = intOrDie(ev.ask, "ask", ev.t_us);
      if (ask < bid + 1) throw new EngineError(`quote at ${ev.t_us}: ask must be >= bid + 1`);
      this.quotes = [bid, ask];
      this.quoteLog.push(ev);
      return null;
    }

    if (ev.type === "jump") {
      if (intOrDie(ev.size, "size", ev.t_us) === 0) {
        throw new EngineError(`jump at ${ev.t_us}: size must be nonzero`);
      }
      this.v += ev.size;
      this.jumps.push(ev);
      return null;
    }

    if (ev.type === "arrival") {
      if (this.quotes === null) throw new EngineError(`arrival at ${ev.t_us} with no quote set (§1.2)`);
      const [bid, ask] = this.quotes;
      if (ev.trader === "informed") {
        if (ev.side_intent !== null || ev.u_accept !== null) {
          throw new EngineError(`arrival at ${ev.t_us}: informed arrivals carry null side_intent/u_accept (D5)`);
        }
        // Strict inequalities; ties decline (§1.3).
        if (ask < this.v) return this.doFill(ev.t_us, "buy", ask, "informed", bid, ask);
        if (bid > this.v) return this.doFill(ev.t_us, "sell", bid, "informed", bid, ask);
        return this.doDecline(ev.t_us, "informed", null, "v_inside_quotes");
      }
      if (ev.trader === "noise") {
        if (ev.side_intent !== "buy" && ev.side_intent !== "sell") {
          throw new EngineError(`arrival at ${ev.t_us}: bad noise side_intent ${String(ev.side_intent)}`);
        }
        const u = ev.u_accept;
        if (typeof u !== "number" || !(u >= 0 && u < 1)) {
          throw new EngineError(`arrival at ${ev.t_us}: u_accept must be in [0, 1), got ${String(u)}`);
        }
        // noise: accepts iff u_accept < f(h) (§1.3)
        if (u < noiseAcceptProb(bid, ask, this.params.delta0)) {
          const price = ev.side_intent === "buy" ? ask : bid;
          return this.doFill(ev.t_us, ev.side_intent, price, "noise", bid, ask);
        }
        return this.doDecline(ev.t_us, "noise", ev.side_intent, "balked_at_spread");
      }
      throw new EngineError(`arrival at ${ev.t_us}: trader must be informed/noise`);
    }

    throw new EngineError(`unknown event ${JSON.stringify(ev)}`);
  }

  private doFill(
    t_us: number,
    side: "buy" | "sell",
    price: number,
    trader: "informed" | "noise",
    bid: number,
    ask: number,
  ): Fill {
    const f: Fill = { t_us, side, price, v_at_fill: this.v, trader, bid, ask };
    const q = fillQ(f);
    this.cash -= q * price;
    this.inventory += q;
    this.fills.push(f);
    return f;
  }

  private doDecline(
    t_us: number,
    trader: "informed" | "noise",
    side_intent: "buy" | "sell" | null,
    reason: "v_inside_quotes" | "balked_at_spread",
  ): Decline {
    const d: Decline = { t_us, trader, side_intent, reason };
    this.declines.push(d);
    return d;
  }

  finalize(): RoundResult {
    this.finalized = true;
    return {
      params: this.params,
      fills: this.fills,
      declines: this.declines,
      jumps: this.jumps,
      quotes: this.quoteLog,
      v_terminal: this.v,
      cash: this.cash,
      inventory: this.inventory,
    };
  }
}

/** Replay mode: consume a complete (vector-style) stream. */
export function runStream(params: SimParams, events: StreamEvent[]): RoundResult {
  const eng = new Engine(params);
  for (const ev of events) eng.apply(ev);
  return eng.finalize();
}
