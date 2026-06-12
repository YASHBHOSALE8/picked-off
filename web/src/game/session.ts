/**
 * "Download my session" (DESIGN.md §7.3): the full round — params, stream
 * id, every player quote event, fills, the revealed stream, decomposition —
 * serialized client-side via Blob. No backend, no telemetry, ever.
 */

import type { FinishedRound } from "./live";

export function sessionJson(round: FinishedRound): string {
  const { result, decomp, fillScores } = round;
  return JSON.stringify(
    {
      meta: {
        game: "picked-off",
        session_version: 1,
        level: round.level,
        stream_id: round.streamId,
        params: result.params,
        exported_at: new Date().toISOString(),
      },
      player_quotes: result.quotes,
      fills: result.fills.map((f, i) => ({
        ...f,
        sc_half: fillScores[i].sc_half,
        as_half: fillScores[i].as_half,
        ic_half: fillScores[i].ic_half,
        markout_1s: fillScores[i].markout_1s,
        markout_5s: fillScores[i].markout_5s,
      })),
      revealed: {
        declines: result.declines,
        jumps: result.jumps,
      },
      v_terminal: result.v_terminal,
      inventory_terminal: result.inventory,
      cash_terminal: result.cash,
      pnl_decomposition_half_ticks: decomp,
    },
    null,
    1,
  );
}

export function downloadSession(round: FinishedRound): void {
  const blob = new Blob([sessionJson(round)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `picked-off-${round.streamId}-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
