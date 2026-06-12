/**
 * PnL decomposition, markouts, and the exact accounting identity
 * (DESIGN.md §2). Mirror of sim/picked_off/scoring.py.
 *
 * All decomposition arithmetic is in integer half-ticks. Two identities are
 * asserted with exact integer equality, no tolerance, on every scored round:
 *   1. total == SC + AS + IC == 2 * (cash_T + inv_T * V_T)   (§2.2)
 *   2. IC == 2 * sum over jumps of J_k * inv(t_k-)           (jump form)
 * V(t) lookups use the càdlàg convention (a jump at exactly s is included).
 */

import { fillQ, type RoundResult } from "./engine";
import type { JumpEvent } from "./events";
import { MARKOUT_HORIZONS_US } from "./params";

export class ScoringError extends Error {}

/** Normalize JS negative zero (q * 0 === -0) to +0 so signed-product terms
 * match Python integers exactly under Object.is-style comparison. */
const z = (x: number): number => (x === 0 ? 0 : x);

export interface FillScore {
  t_us: number;
  q: number;
  sc_half: number;
  as_half: number;
  ic_half: number;
  markout_1s: number;
  markout_5s: number;
}

export interface Decomposition {
  total: number;
  spread_captured: number;
  adverse_selection: number;
  inventory_cost: number;
}

/** V(t) on the càdlàg convention: jumps with t_k <= t_us are included. */
export function valueAt(v0: number, jumps: JumpEvent[], tUs: number): number {
  let v = v0;
  for (const j of jumps) {
    if (j.t_us > tUs) break; // jumps are time-ordered
    v += j.size;
  }
  return v;
}

export function scoreRound(result: RoundResult): { decomp: Decomposition; fillScores: FillScore[] } {
  const p = result.params;
  const vT = result.v_terminal;
  const fillScores: FillScore[] = [];
  let sc = 0;
  let as = 0;
  let ic = 0;

  for (const f of result.fills) {
    const q = fillQ(f);
    const scI = f.ask - f.bid; // q*(m-p) ticks == (a-b)/2 ticks == a-b half-ticks
    const asI = z(q * (2 * f.v_at_fill - f.ask - f.bid));
    const icI = z(2 * q * (vT - f.v_at_fill));
    const mo = MARKOUT_HORIZONS_US.map(
      (tau) => z(q * (valueAt(p.v0, result.jumps, Math.min(f.t_us + tau, p.round_us)) - f.price)),
    );
    fillScores.push({ t_us: f.t_us, q, sc_half: scI, as_half: asI, ic_half: icI, markout_1s: mo[0], markout_5s: mo[1] });
    sc += scI;
    as += asI;
    ic += icI;
  }

  const total = sc + as + ic;

  // Identity 1 (§2.2): exact integer equality, no tolerance.
  const pnlHalf = 2 * (result.cash + result.inventory * vT);
  if (total !== pnlHalf) {
    throw new ScoringError(`identity violated: SC+AS+IC = ${total} half-ticks but 2*PnL = ${pnlHalf}`);
  }

  // Identity 2 (§2.2): IC == sum over jumps of J_k * inv just before the jump.
  let icJumpForm = 0;
  let fillIdx = 0;
  let inv = 0;
  for (const j of result.jumps) {
    while (fillIdx < result.fills.length && result.fills[fillIdx].t_us < j.t_us) {
      inv += fillQ(result.fills[fillIdx]);
      fillIdx += 1;
    }
    icJumpForm += j.size * inv;
  }
  if (ic !== 2 * icJumpForm) {
    throw new ScoringError(`IC jump-form mismatch: per-fill ${ic} half-ticks vs jump-form ${2 * icJumpForm}`);
  }

  return { decomp: { total, spread_captured: sc, adverse_selection: as, inventory_cost: ic }, fillScores };
}

/** Port of generator.expected_output: the §6.2 expected_output block. */
export function expectedOutput(result: RoundResult): Record<string, unknown> {
  const { decomp, fillScores } = scoreRound(result);
  return {
    fills: result.fills.map((f, i) => ({
      t_us: f.t_us,
      side: f.side,
      price: f.price,
      v_at_fill: f.v_at_fill,
      trader: f.trader,
      markout_1s: fillScores[i].markout_1s,
      markout_5s: fillScores[i].markout_5s,
    })),
    declines: result.declines.map((d) => ({
      t_us: d.t_us,
      trader: d.trader,
      side_intent: d.side_intent,
      reason: d.reason,
    })),
    v_terminal: result.v_terminal,
    inventory_terminal: result.inventory,
    cash_terminal: result.cash,
    pnl_decomposition_half_ticks: { ...decomp },
  };
}
