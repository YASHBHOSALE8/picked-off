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

## Auto-deploy on push: ⚠ NOT yet connected — one manual step for you

`vercel link`'s automatic `git connect` failed: *"Failed to connect YASHBHOSALE8/picked-off to project"* — the Vercel GitHub App isn't installed on your GitHub account, and installing a GitHub App grants repo access that only you should authorize. The 3-click fallback:

1. Open <https://vercel.com/yashbhosale1954-4788/picked-off/settings/git>
2. Click **Connect Git Repository** → **GitHub** (a GitHub window asks you to install/authorize the **Vercel** app — grant it access to `picked-off`, "Only select repositories" is fine)
3. Pick `YASHBHOSALE8/picked-off` → Connect.

After that, every push to `main` auto-deploys to production (the committed `vercel.json` governs the build). Until then, deploy manually with `npx vercel deploy --prod` from the repo root.

## Anything else manual

- Nothing for the deployment itself — it is live now.
- Outstanding from step ⑤ (unchanged, see REPORT3): README screenshot + replay GIF, `writeup/`, playtest pass.

## Footprint notes

- No secrets are tracked (scanned tracked files and content before publishing; `.vercel/` is git-ignored, the CLI appended `.vercel` to `.gitignore` and that change is committed here).
- User-space tooling added this session: `~/.local/ghcli` (gh). Previously: `~/.local/node22` (Node 22). Neither touches system paths.
