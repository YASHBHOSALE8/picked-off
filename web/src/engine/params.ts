/**
 * Simulation parameters and the level table (DESIGN.md §1.5, FINAL v1.1).
 * Mirror of sim/picked_off/params.py — the Python sim is the source of truth.
 */

export const TICK_GRID_US = 100_000;
export const MARKOUT_HORIZONS_US = [1_000_000, 5_000_000] as const;

/** Final gate-selected regime (DESIGN.md §1.5): alpha escalates per level. */
export const LEVEL_ALPHAS: Record<number, number> = {
  1: 0.1,
  2: 0.2,
  3: 0.3,
  4: 0.4,
  5: 0.5,
};

export interface SimParams {
  v0: number;
  round_us: number;
  lambda_j: number;
  p_jump: number;
  lambda_a: number;
  alpha: number;
  delta0: number;
}

const PARAM_KEYS = ["v0", "round_us", "lambda_j", "p_jump", "lambda_a", "alpha", "delta0"];

export function paramsForLevel(level: number): SimParams {
  const alpha = LEVEL_ALPHAS[level];
  if (alpha === undefined) throw new Error(`no such level: ${level}`);
  return { v0: 10_000, round_us: 60_000_000, lambda_j: 0.2, p_jump: 0.2, lambda_a: 4.0, alpha, delta0: 8.0 };
}

function isNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** Port of SimParams.from_meta + __post_init__ validation. */
export function paramsFromMeta(d: Record<string, unknown>): SimParams {
  const keys = Object.keys(d).sort();
  if (keys.length !== PARAM_KEYS.length || !PARAM_KEYS.slice().sort().every((k, i) => keys[i] === k)) {
    throw new Error(`meta.params keys must be exactly ${PARAM_KEYS.join(",")}, got ${keys.join(",")}`);
  }
  for (const k of PARAM_KEYS) {
    if (!isNumber(d[k])) throw new Error(`meta.params.${k} must be a JSON number, got ${String(d[k])}`);
  }
  const p = d as unknown as SimParams;
  if (!Number.isInteger(p.v0) || p.v0 <= 0) throw new Error(`v0 must be a positive int, got ${p.v0}`);
  if (!Number.isInteger(p.round_us) || p.round_us <= 0) throw new Error(`round_us must be a positive int`);
  if (!(p.p_jump > 0 && p.p_jump <= 1)) throw new Error(`p_jump must be in (0, 1], got ${p.p_jump}`);
  if (p.lambda_j < 0 || p.lambda_a < 0) throw new Error("lambda_j and lambda_a must be >= 0");
  if (!(p.alpha >= 0 && p.alpha <= 1)) throw new Error(`alpha must be in [0, 1], got ${p.alpha}`);
  if (!(p.delta0 > 0)) throw new Error(`delta0 must be > 0, got ${p.delta0}`);
  return { ...p };
}
