export function HomeScreen({ onPlay, onTutorial }: { onPlay: () => void; onTutorial: () => void }) {
  return (
    <div className="screen home">
      <div className="home-center">
        <h1 className="home-title">PICKED OFF</h1>
        <p className="home-pitch">
          You're the dealer. Quote a two-sided market against a hidden fair value — and figure out
          who knows something you don't.
        </p>
        <div className="home-btns">
          <button className="btn primary big" onClick={onPlay}>
            PLAY
          </button>
          <button className="btn big" onClick={onTutorial}>
            HOW IT WORKS
          </button>
        </div>
      </div>
      <footer className="foot home-foot">
        <a
          href="https://github.com/YASHBHOSALE8/picked-off/blob/main/writeup/writeup.md"
          target="_blank"
          rel="noreferrer"
        >
          writeup
        </a>{" "}
        ·{" "}
        <a href="https://github.com/YASHBHOSALE8/picked-off" target="_blank" rel="noreferrer">
          github
        </a>
      </footer>
    </div>
  );
}
