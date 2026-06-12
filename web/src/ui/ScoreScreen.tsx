import type { FinishedRound } from "../game/live";
import { downloadSession } from "../game/session";
import { halfTicksToUsd } from "./format";

function Row({ label, half, note }: { label: string; half: number; note: string }) {
  const cls = half > 0 ? "pos" : half < 0 ? "neg" : "";
  return (
    <div className="score-row">
      <span className="score-label">{label}</span>
      <span className={`score-num ${cls}`}>{halfTicksToUsd(half)}</span>
      <span className="score-note">{note}</span>
    </div>
  );
}

export function ScoreScreen({
  round,
  onReplay,
  onAgain,
  onMenu,
}: {
  round: FinishedRound;
  onReplay: () => void;
  onAgain: () => void;
  onMenu: () => void;
}) {
  const d = round.decomp;
  const r = round.result;
  const pickoffs = r.fills.filter((f) => f.trader === "informed").length;
  return (
    <div className="screen score">
      <h2>ROUND CLOSED — L{round.level}</h2>
      <div className={`score-total ${d.total >= 0 ? "pos" : "neg"}`}>{halfTicksToUsd(d.total)}</div>
      <div className="score-sub">
        {r.fills.length} fills · {r.declines.length} walked away · {pickoffs} pick-offs · terminal
        inventory {r.inventory > 0 ? `+${r.inventory}` : r.inventory}
      </div>
      <div className="score-table">
        <Row label="Spread captured" half={d.spread_captured} note="half the spread, every fill" />
        <Row label="Adverse selection" half={d.adverse_selection} note="how far value was past your mid" />
        <Row label="Inventory cost" half={d.inventory_cost} note="jumps against what you held" />
        <div className="score-rule" />
        <Row label="Total" half={d.total} note="sums exactly — that's the identity" />
      </div>
      <div className="btn-row">
        <button className="btn primary" onClick={onReplay}>
          Watch the replay
        </button>
        <button className="btn" onClick={onAgain}>
          Play again
        </button>
        <button className="btn" onClick={onMenu}>
          Levels
        </button>
        <button className="btn" onClick={() => downloadSession(round)}>
          Download my session
        </button>
      </div>
    </div>
  );
}
