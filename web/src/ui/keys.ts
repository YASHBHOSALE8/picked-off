/** Keyboard quote control (desktop). One place to remap. */

export const KEYMAP = {
  askUp: "w",
  askDown: "s",
  bidUp: "p",
  bidDown: "l",
} as const;

export const KEY_STEP = 1; // ticks per press (hold = OS key-repeat)
export const KEY_STEP_SHIFT = 5; // with Shift held

export const KEY_HINTS = {
  ask: "W/S",
  bid: "P/L",
  modifier: "shift ±5",
};

/** Touch-first devices hide the hints (no keyboard assumed). */
export function hasFinePointer(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(pointer: fine)").matches;
}
