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

/** Plain-English, sign-aware one-liners for each component. */
function notes(round: FinishedRound): { sc: string; as: string; ic: string } {
  const d = round.decomp;
  const fills = round.result.fills.length;
  const pickoffs = round.result.fills.filter((f) => f.trader === "informed").length;
  const usd = (h: number) => halfTicksToUsd(Math.abs(h)).replace(/^[+−]/, "");

  const sc =
    fills === 0
      ? "No fills — no spread income. Nobody traded with you."
      : `The bid-ask gap paid you ${usd(d.spread_captured)} across ${fills} fill${fills === 1 ? "" : "s"}.`;

  const as =
    d.adverse_selection < 0
      ? `Informed traders took ${usd(d.adverse_selection)} from you${
          pickoffs ? ` over ${pickoffs} pick-off${pickoffs === 1 ? "" : "s"}` : ""
        } — the value had already moved when they hit your quote.`
      : d.adverse_selection === 0
        ? "Nobody traded through a stale quote. Clean."
        : `Adverse selection went your way for once: fills landed on the right side of value, +${usd(d.adverse_selection)}.`;

  const ic =
    d.inventory_cost < 0
      ? `Value jumps moved against what you were holding — ${usd(d.inventory_cost)} gone by the close.`
      : d.inventory_cost === 0
        ? "Holding inventory cost you nothing this round."
        : `Value jumps drifted with your inventory: +${usd(d.inventory_cost)} of luck, not skill.`;

  return { sc, as, ic };
}

export function ScoreScreen({
  round,
  onReplay,
  onAgain,
  onMenu,
  onHome,
}: {
  round: FinishedRound;
  onReplay: () => void;
  onAgain: () => void;
  onMenu: () => void;
  onHome: () => void;
}) {
  const d = round.decomp;
  const r = round.result;
  const isTutorial = round.level === 0;
  const pickoffs = r.fills.filter((f) => f.trader === "informed").length;
  const n = notes(round);
  return (
    <div className="screen score">
      <button className="link-btn home-link" onClick={onHome}>
        ← Home
      </button>
      <h2>{isTutorial ? "PRACTICE CLOSED" : `ROUND CLOSED — L${round.level}`}</h2>
      <div className={`score-total ${d.total >= 0 ? "pos" : "neg"}`}>{halfTicksToUsd(d.total)}</div>
      <div className="score-sub">
        {r.fills.length} fills · {r.declines.length} walked away · {pickoffs} pick-offs · terminal
        inventory {r.inventory > 0 ? `+${r.inventory}` : r.inventory}
      </div>
      <div className="score-table">
        <Row label="Spread captured" half={d.spread_captured} note={n.sc} />
        <Row label="Adverse selection" half={d.adverse_selection} note={n.as} />
        <Row label="Inventory cost" half={d.inventory_cost} note={n.ic} />
        <div className="score-rule" />
        <Row label="Total" half={d.total} note="The three sum exactly — that's the identity." />
      </div>
      <div className="btn-row">
        <button className="btn primary" onClick={onReplay}>
          Watch the replay
        </button>
        <button className="btn" onClick={onAgain}>
          {isTutorial ? "To the real thing" : "Play again"}
        </button>
        <button className="btn" onClick={onMenu}>
          Levels
        </button>
        <button className="btn" onClick={onHome}>
          Home
        </button>
        <button className="btn" onClick={() => downloadSession(round)}>
          Download my session
        </button>
      </div>
    </div>
  );
}
