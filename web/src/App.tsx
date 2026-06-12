import { useCallback, useState } from "react";
import { LiveRound, type FinishedRound } from "./game/live";
import { pickStream } from "./game/pool";
import { LevelSelect } from "./ui/LevelSelect";
import { LiveScreen } from "./ui/LiveScreen";
import { ReplayScreen } from "./ui/ReplayScreen";
import { ScoreScreen } from "./ui/ScoreScreen";

type Screen = "menu" | "loading" | "live" | "score" | "replay" | "error";

export default function App() {
  const [screen, setScreen] = useState<Screen>("menu");
  const [live, setLive] = useState<LiveRound | null>(null);
  const [done, setDone] = useState<FinishedRound | null>(null);
  const [error, setError] = useState("");

  const play = useCallback(async (level: number) => {
    setScreen("loading");
    try {
      const doc = await pickStream(level);
      setLive(new LiveRound(doc));
      setDone(null);
      setScreen("live");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setScreen("error");
    }
  }, []);

  const onDone = useCallback((f: FinishedRound) => {
    setDone(f);
    setScreen("score");
  }, []);

  switch (screen) {
    case "menu":
      return <LevelSelect onPick={play} />;
    case "loading":
      return (
        <div className="screen center">
          <p className="dim">fetching a round…</p>
        </div>
      );
    case "live":
      return live ? <LiveScreen round={live} onDone={onDone} /> : null;
    case "score":
      return done ? (
        <ScoreScreen
          round={done}
          onReplay={() => setScreen("replay")}
          onAgain={() => play(done.level)}
          onMenu={() => setScreen("menu")}
        />
      ) : null;
    case "replay":
      return done ? (
        <ReplayScreen round={done} onBack={() => setScreen("score")} onMenu={() => setScreen("menu")} />
      ) : null;
    case "error":
      return (
        <div className="screen center">
          <p className="neg">{error}</p>
          <button className="btn" onClick={() => setScreen("menu")}>
            Back
          </button>
        </div>
      );
  }
}
