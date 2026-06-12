import { useCallback, useEffect, useRef, useState } from "react";
import { LiveRound, type FinishedRound } from "./game/live";
import { loadStream, pickStream } from "./game/pool";
import { LevelSelect } from "./ui/LevelSelect";
import { LiveScreen } from "./ui/LiveScreen";
import { ReplayScreen } from "./ui/ReplayScreen";
import { ScoreScreen } from "./ui/ScoreScreen";
import { markTutorialDone, TUTORIAL_STREAM_ID, tutorialDone } from "./ui/tutorial";

type Screen = "menu" | "loading" | "live" | "tutorial" | "score" | "replay" | "error";

export default function App() {
  const [screen, setScreen] = useState<Screen>("menu");
  const [live, setLive] = useState<LiveRound | null>(null);
  const [done, setDone] = useState<FinishedRound | null>(null);
  const [error, setError] = useState("");
  const bootRef = useRef(false);

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

  const startTutorial = useCallback(async () => {
    setScreen("loading");
    try {
      const doc = await loadStream(TUTORIAL_STREAM_ID);
      setLive(new LiveRound(doc));
      setDone(null);
      setScreen("tutorial");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setScreen("error");
    }
  }, []);

  // First visit: run the tutorial once (skippable; never reappears after).
  useEffect(() => {
    if (bootRef.current) return;
    bootRef.current = true;
    if (!tutorialDone()) void startTutorial();
  }, [startTutorial]);

  const onDone = useCallback((f: FinishedRound) => {
    setDone(f);
    setScreen("score");
  }, []);

  const onTutorialDone = useCallback((f: FinishedRound) => {
    markTutorialDone();
    setDone(f);
    setScreen("score");
  }, []);

  const skipTutorial = useCallback(() => {
    markTutorialDone();
    setScreen("menu");
  }, []);

  switch (screen) {
    case "menu":
      return <LevelSelect onPick={play} onTutorial={startTutorial} />;
    case "loading":
      return (
        <div className="screen center">
          <p className="dim">fetching a round…</p>
        </div>
      );
    case "live":
      return live ? <LiveScreen round={live} onDone={onDone} /> : null;
    case "tutorial":
      return live ? (
        <LiveScreen round={live} onDone={onTutorialDone} tutorial onSkip={skipTutorial} />
      ) : null;
    case "score":
      return done ? (
        <ScoreScreen
          round={done}
          onReplay={() => setScreen("replay")}
          onAgain={() => (done.level === 0 ? setScreen("menu") : play(done.level))}
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
