import { LEVEL_ALPHAS } from "../engine/params";

const LEVEL_COPY: Record<number, { name: string; copy: string; edge: string }> = {
  1: {
    name: "Tourists",
    copy: "One in ten knows what it's worth. A sensible spread prints money — quote wide, stay calm.",
    edge: "naive play works here",
  },
  2: {
    name: "Regulars",
    copy: "One in five is informed. Spread income still covers the pick-offs, barely.",
    edge: "reading the tape starts to pay",
  },
  3: {
    name: "Sharps",
    copy: "Three in ten know the number. Watch who trades — and notice who doesn't.",
    edge: "information edge ×1.35",
  },
  4: {
    name: "Wolves",
    copy: "Almost half the flow is informed. Silence is a message. Quiet markets are a warning.",
    edge: "information edge ×1.74",
  },
  5: {
    name: "Toxic",
    copy: "Half of everyone at your quote knows exactly what it's worth. The water is toxic. Spread alone will not save you.",
    edge: "information edge ×3.05",
  },
};

export function LevelSelect({
  onPick,
  onTutorial,
}: {
  onPick: (level: number) => void;
  onTutorial: () => void;
}) {
  return (
    <div className="screen menu">
      <header className="masthead">
        <h1>PICKED OFF</h1>
        <p className="sub">
          You are the dealer. Quote a two-sided market against a hidden fair value. Part of the
          flow knows it exactly — and the ones who walk away without trading are telling you
          something too.
        </p>
      </header>
      <div className="levels">
        {Object.keys(LEVEL_ALPHAS).map((k) => {
          const level = Number(k);
          const c = LEVEL_COPY[level];
          return (
            <button key={level} className="level-card" onClick={() => onPick(level)}>
              <div className="level-row">
                <span className="level-num">L{level}</span>
                <span className="level-name">{c.name}</span>
                <span className="level-alpha">α = {LEVEL_ALPHAS[level].toFixed(2)}</span>
              </div>
              <p className="level-copy">{c.copy}</p>
              <span className="level-edge">{c.edge}</span>
            </button>
          );
        })}
      </div>
      <footer className="foot">
        60-second rounds · one unit per fill · declines are invisible until the replay ·{" "}
        <button className="link-btn" onClick={onTutorial}>
          ? replay the 30s tutorial
        </button>{" "}
        ·{" "}
        <a href="https://github.com/YASHBHOSALE8/picked-off" target="_blank" rel="noreferrer">
          how it works
        </a>
      </footer>
    </div>
  );
}
