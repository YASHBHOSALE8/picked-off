/** Minimal history-API routing. Routes:
 *    /            home
 *    /levels      level select
 *    /play/:level live round (cold load starts a fresh round)
 *    /tutorial    the scripted practice round
 *    /score       score screen   (redirects home without round state)
 *    /replay      replay screen  (redirects home without round state)
 * Unknown paths resolve to home (never a blank screen).
 */

export type Route =
  | { name: "home" }
  | { name: "levels" }
  | { name: "play"; level: number }
  | { name: "tutorial" }
  | { name: "score" }
  | { name: "replay" };

export function parsePath(pathname: string): Route {
  const m = pathname.match(/^\/play\/([1-5])\/?$/);
  if (m) return { name: "play", level: Number(m[1]) };
  switch (pathname.replace(/\/+$/, "") || "/") {
    case "/levels":
      return { name: "levels" };
    case "/tutorial":
      return { name: "tutorial" };
    case "/score":
      return { name: "score" };
    case "/replay":
      return { name: "replay" };
    default:
      return { name: "home" };
  }
}

export function pathFor(r: Route): string {
  switch (r.name) {
    case "home":
      return "/";
    case "play":
      return `/play/${r.level}`;
    default:
      return `/${r.name}`;
  }
}
