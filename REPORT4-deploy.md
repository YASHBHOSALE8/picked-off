# REPORT4 — Publish + deploy

Date: 2026-06-12.

## Where things live

- **GitHub:** <https://github.com/YASHBHOSALE8/picked-off> — **private** (flip to public after final polish: `gh repo edit --visibility public --accept-visibility-change-consequences`, or Settings → Danger Zone). `main` pushed with upstream tracking; 4 commits + this one.
- **Live site:** <https://picked-off.vercel.app> — production, status Ready, project `picked-off` under account `yashbhosale1954-4788`.

## Verified (curl, post-deploy)

- `GET /` → 200, serves the game (`<title>Picked Off — a market-making game</title>`).
- `GET /streams/index.json` → 200, 5 levels × 40 streams.
- `GET /streams/L1-600000.json` → 200, 27 KB — pool assets load.

## How it was done

- `gh` CLI v2.94.0 installed **user-space** at `~/.local/ghcli` (no sudo/Homebrew; remove with `rm -rf ~/.local/ghcli`). GitHub auth via the OAuth **device flow** (the interactive `gh auth login` prompts can't run without a TTY); token went directly into gh's keychain, never printed. Git pushes use gh as the https credential helper.
- Repo created + pushed in one step: `gh repo create picked-off --private --source . --push`.
- Vercel CLI via `npx vercel@latest` (nothing installed globally). Login completed through the browser session; project linked non-interactively (`vercel link --yes --project picked-off`) and deployed with `vercel deploy --prod --yes`. Build config comes from the committed root `vercel.json` (install `cd web && npm ci`, build `cd web && npm run build`, output `web/dist`) — no dashboard configuration was needed for the build.

## Auto-deploy on push: ✅ CONNECTED

`vercel link`'s automatic `git connect` initially failed (the Vercel GitHub App wasn't installed — that authorization is a user-only action). Connected manually via the dashboard (Project Settings → Git → Connect Git Repository → `YASHBHOSALE8/picked-off`) on 2026-06-12. Every push to `main` now auto-deploys to production; the committed `vercel.json` governs the build. The commit adding this very paragraph was the first end-to-end test of the pipeline — and it caught a real issue: Vercel **blocks** deployments whose commit author email isn't associated with the GitHub account. The repo's git identity is now pinned locally to the account email (`git config user.email Yashbhosale1954@gmail.com`); earlier commits (①–④ and the deploy commit pre-amend) carry the old email but only affect already-deployed history, which Vercel does not retro-block.

## Anything else manual

- Nothing for the deployment itself — it is live with auto-deploy on push.
- Outstanding from step ⑤ (unchanged, see REPORT3): README screenshot + replay GIF, `writeup/`, playtest pass.

## Footprint notes

- No secrets are tracked (scanned tracked files and content before publishing; `.vercel/` is git-ignored, the CLI appended `.vercel` to `.gitignore` and that change is committed here).
- User-space tooling added this session: `~/.local/ghcli` (gh). Previously: `~/.local/node22` (Node 22). Neither touches system paths.
