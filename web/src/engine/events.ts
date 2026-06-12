/**
 * Event types and stream parsing/validation (DESIGN.md §6.2, §0).
 * Mirror of sim/picked_off/events.py. Fails loudly per §6.3-4.
 */

export class StreamError extends Error {}

export interface QuoteEvent {
  type: "quote";
  t_us: number;
  bid: number;
  ask: number;
}

export interface JumpEvent {
  type: "jump";
  t_us: number;
  size: number;
}

export interface ArrivalEvent {
  type: "arrival";
  t_us: number;
  trader: "informed" | "noise";
  side_intent: "buy" | "sell" | null;
  u_accept: number | null;
}

export type StreamEvent = QuoteEvent | JumpEvent | ArrivalEvent;

function strictInt(value: unknown, what: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new StreamError(`${what} must be an integer, got ${String(value)}`);
  }
  return value;
}

function exactKeys(d: object, keys: string[], what: string): void {
  const got = Object.keys(d).sort();
  const want = keys.slice().sort();
  if (got.length !== want.length || !want.every((k, i) => got[i] === k)) {
    throw new StreamError(`${what} fields must be exactly ${want.join("/")}, got ${got.join("/")}`);
  }
}

/** Port of events.parse_event: strict field/type validation per §6.2. */
export function parseEvent(d: Record<string, unknown>): StreamEvent {
  if (typeof d !== "object" || d === null || Array.isArray(d)) {
    throw new StreamError("event must be an object");
  }
  const t_us = strictInt(d.t_us, "t_us");
  const etype = d.type;

  if (etype === "quote") {
    exactKeys(d, ["t_us", "type", "bid", "ask"], "quote event");
    const bid = strictInt(d.bid, "bid");
    const ask = strictInt(d.ask, "ask");
    if (ask < bid + 1) throw new StreamError(`quote at t_us=${t_us}: ask must be >= bid + 1`);
    return { type: "quote", t_us, bid, ask };
  }

  if (etype === "jump") {
    exactKeys(d, ["t_us", "type", "size"], "jump event");
    const size = strictInt(d.size, "size");
    if (size === 0) throw new StreamError(`jump at t_us=${t_us}: size must be nonzero`);
    return { type: "jump", t_us, size };
  }

  if (etype === "arrival") {
    exactKeys(d, ["t_us", "type", "trader", "side_intent", "u_accept"], "arrival event");
    const trader = d.trader;
    const side = d.side_intent;
    const u = d.u_accept;
    if (trader === "informed") {
      if (side !== null || u !== null) {
        throw new StreamError(`arrival at t_us=${t_us}: informed arrivals must have null side_intent/u_accept (D5)`);
      }
      return { type: "arrival", t_us, trader, side_intent: null, u_accept: null };
    }
    if (trader === "noise") {
      if (side !== "buy" && side !== "sell") {
        throw new StreamError(`arrival at t_us=${t_us}: noise side_intent must be buy/sell, got ${String(side)}`);
      }
      if (typeof u !== "number" || !(u >= 0 && u < 1)) {
        throw new StreamError(`arrival at t_us=${t_us}: u_accept must be a float in [0, 1), got ${String(u)}`);
      }
      return { type: "arrival", t_us, trader, side_intent: side, u_accept: u };
    }
    throw new StreamError(`arrival at t_us=${t_us}: trader must be informed/noise, got ${String(trader)}`);
  }

  throw new StreamError(`unknown event type ${String(etype)} at t_us=${String(d.t_us)}`);
}

/** Port of events.validate_stream (§0 rule 2, §6.2). */
export function validateStream(events: StreamEvent[], roundUs: number, requireOpeningQuote = true): void {
  let lastT = -1;
  let quoted = false;
  for (const ev of events) {
    if (ev.t_us <= lastT) {
      throw new StreamError(`timestamps must be strictly increasing: ${ev.t_us} after ${lastT}`);
    }
    if (!(ev.t_us >= 0 && ev.t_us < roundUs)) {
      throw new StreamError(`t_us=${ev.t_us} outside [0, ${roundUs})`);
    }
    lastT = ev.t_us;
    if (ev.type === "quote") quoted = true;
    else if (ev.type === "arrival" && requireOpeningQuote && !quoted) {
      throw new StreamError(`arrival at t_us=${ev.t_us} before any quote`);
    }
  }
  if (requireOpeningQuote) {
    if (events.length === 0) throw new StreamError("vector stream must contain at least the opening quote");
    const first = events[0];
    if (first.type !== "quote" || first.t_us !== 0) {
      throw new StreamError("first stream event must be a quote at t_us = 0");
    }
  }
}

export function parseStream(raw: unknown, roundUs: number, requireOpeningQuote = true): StreamEvent[] {
  if (!Array.isArray(raw)) throw new StreamError("event_stream must be an array");
  const events = raw.map((d) => parseEvent(d as Record<string, unknown>));
  validateStream(events, roundUs, requireOpeningQuote);
  return events;
}
