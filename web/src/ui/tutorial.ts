/** Tutorial copy + step logic (first-visit onboarding, ~30 s).
 * The tutorial round runs a dedicated scripted stream
 * (streams/tutorial.json — hand-built with the frozen Python generator's
 * rules, mostly noise plus exactly one informed arrival after a hidden
 * +12 jump).
 */

export const TUTORIAL_DONE_KEY = "po_tutorial_done";

export const TUTORIAL_STREAM_ID = "tutorial";

export interface TutorialCard {
  id: "firstfill" | "spread" | "pickoff" | "nopickoff" | "end";
  title: string;
  body: string;
}

export const CARDS: Record<TutorialCard["id"], TutorialCard> = {
  firstfill: {
    id: "firstfill",
    title: "A fill.",
    body:
      "A customer crossed your spread — you keep the gap between your bid and ask. " +
      "That's spread income. This one was harmless. They aren't all harmless.",
  },
  spread: {
    id: "spread",
    title: "Working the spread",
    body:
      "Tighter quotes attract more customers; wider quotes earn more per fill. " +
      "Nudge with W/S (ask) and P/L (bid), or drag. Keep dealing.",
  },
  pickoff: {
    id: "pickoff",
    title: "That trader knew something you didn't.",
    body:
      "You just got picked off. The value jumped a moment ago — you couldn't see it, they could, " +
      "and your stale quote paid them the difference. This is adverse selection.",
  },
  nopickoff: {
    id: "nopickoff",
    title: "Someone just sized you up — and passed.",
    body:
      "An informed trader looked at your quotes and declined: they happened to straddle the truth. " +
      "You didn't see that either. Silence is information too.",
  },
  end: {
    id: "end",
    title: "Real rounds mix both kinds.",
    body:
      "And you can't tell who's who. Watch the tape, mind the silences, reprice fast. Good luck.",
  },
};

export const TUTORIAL_ARM_TEXT =
  "Practice market — no score, no pressure. The two lines are your quotes: you BUY at your bid, " +
  "SELL at your ask. Drag them (or W/S, P/L), then start the clock and make a market.";

/** The scripted informed arrival lands at 17.2 s; if it declined instead of
 * filling, the fallback card fires shortly after. */
export const NOPICKOFF_FALLBACK_T_US = 19_000_000;

export function tutorialDone(): boolean {
  try {
    return localStorage.getItem(TUTORIAL_DONE_KEY) === "1";
  } catch {
    return true; // storage unavailable -> never force the tutorial
  }
}

export function markTutorialDone(): void {
  try {
    localStorage.setItem(TUTORIAL_DONE_KEY, "1");
  } catch {
    /* fine */
  }
}
