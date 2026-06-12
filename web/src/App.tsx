import { useCallback, useEffect, useRef, useState } from "react";
import { LiveRound, type FinishedRound } from "./game/live";
import { loadStream, pickStream } from "./game/pool";
import { parsePath, pathFor, type Route } from "./router";
import { HomeScreen } from "./ui/HomeScreen";
import { LevelSelect } from "./ui/LevelSelect";
import { LiveScreen } from "./ui/LiveScreen";
import { ReplayScreen } from "./ui/ReplayScreen";
import { ScoreScreen } from "./ui/ScoreScreen";
import { markTutorialDone, TUTORIAL_STREAM_ID, tutorialDone } from "./ui/tutorial";

export default function App() {
  const [route, setRouteState] = useState<Route>(() => parsePath(window.location.pathname));
  const [live, setLive] = useState<LiveRound | null>(null);
  const [done, setDone] = useState<FinishedRound | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [leaveTarget, setLeaveTarget] = useState<Route | null>(null);

  const routeRef = useRef(route);
  routeRef.current = route;
  const liveRef = useRef(live);
  liveRef.current = live;
  const loadTokenRef = useRef(0);
  const bootRef = useRef(false);
  // Monotonic id per LiveRound: keys LiveScreen so a new round remounts it,
  // while App re-renders (e.g. the leave dialog) never reset a running one.
  const liveIdRef = useRef(0);

  const navigate = useCallback((r: Route, replace = false) => {
    const url = pathFor(r);
    if (replace) window.history.replaceState(null, "", url);
    else window.history.pushState(null, "", url);
    setRouteState(r);
  }, []);

  // Browser back/forward. Leaving a LIVE round needs confirmation: cancel
  // the pop by re-pushing the current path, freeze the round, ask.
  useEffect(() => {
    const onPop = () => {
      const next = parsePath(window.location.pathname);
      const cur = routeRef.current;
      const lv = liveRef.current;
      const inLiveRound =
        (cur.name === "play" || cur.name === "tutorial") && lv && lv.started && !lv.finished;
      if (inLiveRound && next.name !== cur.name) {
        if (cur.name === "tutorial") {
          // practice round: leaving is free, nothing to confirm
          setLive(null);
          setRouteState(next);
          return;
        }
        window.history.pushState(null, "", pathFor(cur)); // cancel the pop
        setLeaveTarget(next);
        return;
      }
      setLive(null);
      setRouteState(next);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // First-ever visit: straight into the tutorial; it lands home afterwards.
  useEffect(() => {
    if (bootRef.current) return;
    bootRef.current = true;
    if (!tutorialDone() && routeRef.current.name === "home") {
      navigate({ name: "tutorial" }, true);
    }
  }, [navigate]);

  // Cold-start rounds: /play/:level (or /tutorial) with no matching live round.
  useEffect(() => {
    const needPlay =
      route.name === "play" && (!live || live.finished || live.doc.level !== route.level);
    const needTutorial =
      route.name === "tutorial" && (!live || live.doc.stream_id !== TUTORIAL_STREAM_ID || live.finished);
    if (!needPlay && !needTutorial) return;
    const token = ++loadTokenRef.current;
    setLoading(true);
    setError("");
    const fetchDoc = route.name === "play" ? pickStream(route.level) : loadStream(TUTORIAL_STREAM_ID);
    fetchDoc
      .then((doc) => {
        if (loadTokenRef.current !== token || routeRef.current.name !== route.name) return;
        liveIdRef.current += 1;
        setLive(new LiveRound(doc));
        setDone(null);
      })
      .catch((e) => {
        if (loadTokenRef.current !== token) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (loadTokenRef.current === token) setLoading(false);
      });
  }, [route, live]);

  // /score and /replay without round state: redirect home gracefully.
  useEffect(() => {
    if ((route.name === "score" || route.name === "replay") && !done) {
      navigate({ name: "home" }, true);
    }
  }, [route, done, navigate]);

  const onDone = useCallback(
    (f: FinishedRound) => {
      setDone(f);
      setLive(null);
      navigate({ name: "score" }, true); // replace /play so back goes to levels
    },
    [navigate],
  );

  const onTutorialDone = useCallback(
    (f: FinishedRound) => {
      markTutorialDone();
      setDone(f);
      setLive(null);
      navigate({ name: "score" }, true);
    },
    [navigate],
  );

  const skipTutorial = useCallback(() => {
    markTutorialDone();
    setLive(null);
    navigate({ name: "home" }, true);
  }, [navigate]);

  const requestExitLive = useCallback(() => {
    if (routeRef.current.name === "tutorial") {
      // practice round: leaving is just skipping, no confirm
      markTutorialDone();
      setLive(null);
      navigate({ name: "home" }, true);
      return;
    }
    const lv = liveRef.current;
    if (lv && lv.started && !lv.finished) setLeaveTarget({ name: "home" });
    else {
      setLive(null);
      navigate({ name: "home" });
    }
  }, [navigate]);

  const confirmLeave = useCallback(() => {
    const target = leaveTarget;
    setLeaveTarget(null);
    setLive(null); // abandoned — no score
    if (target) navigate(target, true);
  }, [leaveTarget, navigate]);

  if (error) {
    return (
      <div className="screen center">
        <p className="neg">{error}</p>
        <button
          className="btn"
          onClick={() => {
            setError("");
            setLive(null);
            navigate({ name: "home" }, true);
          }}
        >
          ← Home
        </button>
      </div>
    );
  }

  switch (route.name) {
    case "home":
      return (
        <HomeScreen
          onPlay={() => navigate({ name: "levels" })}
          onTutorial={() => {
            setLive(null);
            navigate({ name: "tutorial" });
          }}
        />
      );
    case "levels":
      return (
        <LevelSelect
          onPick={(level) => {
            setLive(null);
            navigate({ name: "play", level });
          }}
          onTutorial={() => {
            setLive(null);
            navigate({ name: "tutorial" });
          }}
          onHome={() => navigate({ name: "home" })}
        />
      );
    case "play":
    case "tutorial": {
      if (loading || !live) {
        return (
          <div className="screen center">
            <p className="dim">fetching a round…</p>
          </div>
        );
      }
      const isTutorial = route.name === "tutorial";
      return (
        <>
          <LiveScreen
            key={liveIdRef.current}
            round={live}
            onDone={isTutorial ? onTutorialDone : onDone}
            tutorial={isTutorial}
            onSkip={isTutorial ? skipTutorial : undefined}
            onExit={requestExitLive}
            frozen={leaveTarget !== null}
          />
          {leaveTarget && (
            <div className="confirm-dialog">
              <div className="tutorial-card">
                <h3>Leave the round?</h3>
                <p>It counts as abandoned — no score, no replay.</p>
                <div className="btn-row">
                  <button className="btn primary" onClick={() => setLeaveTarget(null)}>
                    Stay
                  </button>
                  <button className="btn" onClick={confirmLeave}>
                    Leave
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      );
    }
    case "score":
      return done ? (
        <ScoreScreen
          round={done}
          onReplay={() => navigate({ name: "replay" })}
          onAgain={() =>
            done.level === 0 ? navigate({ name: "levels" }) : navigate({ name: "play", level: done.level })
          }
          onMenu={() => navigate({ name: "levels" })}
          onHome={() => navigate({ name: "home" })}
        />
      ) : null;
    case "replay":
      return done ? (
        <ReplayScreen
          round={done}
          onBack={() => window.history.back()}
          onMenu={() => navigate({ name: "levels" })}
          onHome={() => navigate({ name: "home" })}
        />
      ) : null;
  }
}
