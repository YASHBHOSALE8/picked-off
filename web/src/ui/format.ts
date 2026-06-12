/** Display helpers. Internal units: ticks ($0.01) and half-ticks ($0.005). */

export function ticksToUsd(ticks: number): string {
  const v = ticks / 100;
  const sign = v < 0 ? "−" : v > 0 ? "+" : "";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}

export function halfTicksToUsd(half: number): string {
  return ticksToUsd(half / 2);
}

export function priceToUsd(ticks: number): string {
  return `$${(ticks / 100).toFixed(2)}`;
}

export function clockMmSs(remainingUs: number): string {
  const s = Math.max(0, Math.ceil(remainingUs / 1_000_000));
  return `0:${String(s).padStart(2, "0")}`;
}

export const COLORS = {
  bg: "#1b1d1f",
  panel: "#232527",
  rule: "#3a3d40",
  text: "#c9ccce",
  dim: "#7e8387",
  buy: "#6fc2d8", // customer lifts the ask
  sell: "#d8b46f", // customer hits the bid
  pickoff: "#d9534f",
  pnlPos: "#79c27a",
  pnlNeg: "#d9534f",
  v: "#e8e9ea",
  bid: "#8fa3b8",
  ask: "#b8a08f",
};
