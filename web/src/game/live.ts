/**
 * Live round controller: wall clock -> game µs, censored public feed, and
 * player quote injection per §0 rule 2 / §7.3 — quote events are stamped at
 * the smallest unoccupied µs strictly after the decision time (the D11
 * rule; pool streams carry the §6.3-5 hygiene guarantees, so the search
 * terminates within two steps).
 *
 * During the round the UI may read ONLY the public feed exposed here:
 * fills, own quotes, clock, position, and spread captured (computable from
 * own fills). V, declines, trader types, and the AS/IC components stay
 * censored until finish() (DESIGN.md §1.4) — surfacing them live would leak
 * the hidden fair value.
 */

import { Engine, type Fill, type RoundResult } from "../engine/engine";
import type { QuoteEvent } from "../engine/events";
import { scoreRound, type Decomposition, type FillScore } from "../engine/scoring";
import type { StreamDoc } from "./pool";

export interface FinishedRound {
  streamId: string;
  level: number;
  result: RoundResult;
  decomp: Decomposition;
  fillScores: FillScore[];
}

export class LiveRound {
  readonly doc: StreamDoc;
  private engine: Engine;
  private idx = 0;
  private appliedT = -1;
  private exoTimes: Set<number>;
  /** Censored public feed. */
  fills: Fill[] = [];
  quoteHistory: QuoteEvent[] = [];
  bid: number;
  ask: number;
  started = false;
  finished: FinishedRound | null = null;

  constructor(doc: StreamDoc) {
    this.doc = doc;
    this.engine = new Engine(doc.params);
    this.exoTimes = new Set(doc.events.map((ev) => ev.t_us));
    // Pre-start default quotes: V0 is public (§1.1), so center on it.
    this.bid = doc.params.v0 - 3;
    this.ask = doc.params.v0 + 3;
  }

  get params() {
    return this.doc.params;
  }

  /** Apply the opening quote at t = 0 (§1.2) and start the clock. */
  start(): void {
    if (this.started) return;
    const q: QuoteEvent = { type: "quote", t_us: 0, bid: this.bid, ask: this.ask };
    this.engine.apply(q);
    this.quoteHistory.push(q);
    this.appliedT = 0;
    this.started = true;
  }

  /** Process all exogenous events with t_us <= tUs (censored: only fills surface). */
  advanceTo(tUs: number): Fill[] {
    const newFills: Fill[] = [];
    const cap = Math.min(tUs, this.params.round_us - 1);
    while (this.idx < this.doc.events.length && this.doc.events[this.idx].t_us <= cap) {
      const ev = this.doc.events[this.idx];
      const outcome = this.engine.apply(ev);
      this.appliedT = ev.t_us;
      this.idx += 1;
      if (outcome !== null && "price" in outcome) {
        this.fills.push(outcome);
        newFills.push(outcome);
      }
    }
    return newFills;
  }

  /**
   * Player quote decision at game-time decisionT: stamped at the smallest
   * unoccupied µs strictly after max(decisionT, last applied event).
   */
  setQuotes(bid: number, ask: number, decisionT: number): void {
    if (!this.started || this.finished) return;
    bid = Math.round(bid);
    ask = Math.round(ask);
    if (ask < bid + 1) return; // UI clamps; ignore degenerate drags
    if (bid === this.bid && ask === this.ask) return;
    let tQ = Math.max(decisionT, this.appliedT) + 1;
    while (this.exoTimes.has(tQ)) tQ += 1; // hygiene: at most 2 bumps
    if (tQ >= this.params.round_us) return; // round over before it could apply
    this.advanceTo(tQ - 1); // keep engine event order strictly increasing
    const q: QuoteEvent = { type: "quote", t_us: tQ, bid, ask };
    this.engine.apply(q);
    this.appliedT = tQ;
    this.quoteHistory.push(q);
    this.bid = bid;
    this.ask = ask;
  }

  /** Spread captured so far, half-ticks — the only live-safe PnL component. */
  scLiveHalf(): number {
    let sc = 0;
    for (const f of this.fills) sc += f.ask - f.bid;
    return sc;
  }

  get position(): number {
    return this.engine.inventory;
  }

  get cash(): number {
    return this.engine.cash;
  }

  /** End of round: apply the rest of the stream, unlock the full log. */
  finish(): FinishedRound {
    if (this.finished) return this.finished;
    this.advanceTo(this.params.round_us - 1);
    const result = this.engine.finalize();
    const { decomp, fillScores } = scoreRound(result);
    this.finished = {
      streamId: this.doc.stream_id,
      level: this.doc.level,
      result,
      decomp,
      fillScores,
    };
    return this.finished;
  }
}
