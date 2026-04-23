# Strategist Cockpit — Backlog

> Maintained by Claude Code. Each task: **Problem · Plan · Test/Acceptance · Blast radius**. Priorities: **P0** = hygiene, unblocks everything · **P1** = code quality / "make it ours" · **P2** = feature gaps · **P3** = future integrations.
>
> Way of working (same as CLAUDE.md): **Investigate → Plan incl. test design → Implement → Thoroughly test → Iterate.** Focus on operational efficiency, security, and coding best practices.

---

## P0 — Hygiene

### T-001 Split the uncommitted working tree into meaningful commits
- **Problem.** Repo is at one "Initial commit" (Feb 12). ~1k lines of real work (Engagements page rewrite, dashboard build script, tests, docs, CSV seed) sit uncommitted. Any rollback destroys everything.
- **Plan.**
  1. Commit existing pre-Claude work as one snapshot: `feat: engagements page redesign + dashboard build script + tests + docs`.
  2. Commit Claude Code ownership additions separately: `chore: add CLAUDE.md, backlog, README polish`.
  3. Push both to `origin/main`.
- **Test / acceptance.** `git log --oneline` shows 3 commits. `git status` clean. `gh repo view` reflects updates.
- **Blast radius.** History-only. No runtime impact.

### T-002 Stop tracking `strategist_cockpit.db`
- **Problem.** SQLite dev DB is in the initial commit (45 KB), even though `*.db` is `.gitignore`d.
- **Plan.** `git rm --cached strategist_cockpit.db`; keep the local file. Commit.
- **Test / acceptance.** File gone from `git ls-files`; re-running `python -m data.seed_database` regenerates it locally.
- **Blast radius.** Local only.

### T-003 Move `build_dashboard.py` into `scripts/`
- **Problem.** 2100-line Lakeview build script sits at repo root, which implies it's app code. It's a one-shot IaC.
- **Plan.** `mkdir scripts && git mv build_dashboard.py scripts/build_dashboard.py`. Update `docs/architecture.md` to point there. Check no one imports it.
- **Test / acceptance.** `python scripts/build_dashboard.py --help` still works. No broken import.
- **Blast radius.** One file move + doc update.

### T-004 Drop stale `tsconfig.tsbuildinfo` from tracking
- **Problem.** Build cache file is tracked and changes on every `npm run build`, polluting diffs.
- **Plan.** Add `src/ui/tsconfig.tsbuildinfo` (or `*.tsbuildinfo`) to `.gitignore`; `git rm --cached` it.
- **Test / acceptance.** `git status` stays clean after `npm run build`.
- **Blast radius.** Local only.

---

## P1 — Code quality / "make it ours"

### T-101 Tighten CORS before sharing the app
- **Problem.** `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` in `src/backend/main.py`. Browser will reject `credentials: true` with `*` anyway, but the combination is a smell and a Security-Questionnaire finding.
- **Plan.** In prod (behind Databricks Apps), same-origin is enforced, so we don't need CORS at all. For local dev with the Vite proxy, we also don't need CORS. Remove the middleware. If needed later, restrict to explicit dev origin (`http://localhost:5173`).
- **Test / acceptance.** `curl -I http://localhost:8000/api/health` returns 200; the React dev server (`npm run dev`) still reaches `/api/*` via the Vite proxy; browser devtools show no CORS errors.
- **Blast radius.** `main.py`. Reversible.

### T-102 Drop unused `databricks_token` from Settings
- **Problem.** `Settings.databricks_token` is defined but never read. `databricks-sdk` already picks up `DATABRICKS_TOKEN` from env.
- **Plan.** Remove the field from `config.py` and from `.env.example`. Confirm no references (`grep -r databricks_token src/`).
- **Test / acceptance.** Unit test suite still green; KA integration test still finds the token.
- **Blast radius.** Config only.

### T-103 Replace the keyword ladder in `chat.py` with a proper prompt + KA
- **Problem.** `_fallback_response()` is ~80 lines of `if/elif` with hardcoded answers — brittle, Cursor-style.
- **Plan.**
  1. When `STRATEGO_ENDPOINT_NAME` is set, keep the KA call.
  2. Replace the fallback with a single short `dev_fallback` that says "Stratego is offline — check `STRATEGO_ENDPOINT_NAME`" and returns a minimal deterministic echo. Don't try to be helpful offline.
  3. Move `data/stratego_context.md` into the KA's knowledge source (external to repo), since it is not loaded by the code today.
- **Test / acceptance.** `test_chat.py` passes; manual check that with env set, answers come from KA; with env unset, single fallback line returned.
- **Blast radius.** `chat.py`, `tests/test_chat.py`.

### T-104 Dedupe canvas activity IDs
- **Problem.** `events`, `market-scouting`, `community-seeding` appear in two positions in `StrategistCanvas.tsx` with identical IDs. Same click → same dialog, regardless of where you clicked.
- **Plan.** Give each position a unique ID (`events-customer`, `events-evangelism`, etc.) and extend `CANVAS_ACTIVITY_KEYWORDS` accordingly. Keep keyword sets identical for now; differentiate later.
- **Test / acceptance.** `test_canvas.py` extended with a case per ID; UI click on each box returns a summary; no React console warning.
- **Blast radius.** Canvas file + router map + tests.

### T-105 Make `seed_database.py` idempotent
- **Problem.** The seeder does `db.query(Engagement).delete()` then re-inserts — every run wipes user edits.
- **Plan.** Only seed when `engagements` is empty. Add `--force` flag for the destructive path. Same for projects.
- **Test / acceptance.** New test `test_seed_preserves_existing`: insert an engagement, run seeder, assert it survives. `--force` still truncates.
- **Blast radius.** `data/seed_database.py` + one test.

### T-106 Lint + type-check in CI
- **Problem.** No linter on Python, no eslint, only `tsc -b` runs during `npm run build`.
- **Plan.**
  - Python: add `ruff` config to `pyproject.toml`; run `ruff check src tests scripts` in a GitHub Action.
  - TS: add eslint with `@typescript-eslint` preset; `npm run lint` script.
  - Wire both into `.github/workflows/ci.yml` (with `pytest` as third step).
- **Test / acceptance.** CI green on a clean PR; `ruff check` and `npm run lint` both return 0 locally.
- **Blast radius.** Config files + one workflow. Zero runtime impact.

### T-107 Normalize quarter strings
- **Problem.** Source data has both `FY25-Q1` and `FY25Q1`. Filters and the Engagements bar chart split by `,` but don't normalize.
- **Plan.** Normalize on read: strip dash between FY and Q. Apply in the seeder and in the Engagements page quarter chart.
- **Test / acceptance.** Unit test for normalizer: `"FY25-Q1, FY25Q2" → ["FY25Q1","FY25Q2"]`.
- **Blast radius.** Seeder + one util.

---

## P2 — Feature gaps (ship after P0/P1)

### T-201 Embed the AI/BI Impact Dashboard at `/impact`
- **Problem.** Dashboard is built in Databricks via `scripts/build_dashboard.py` but there's no page linking users to it. The prompt explicitly flagged embedding dashboards as a past pain point.
- **Plan.**
  1. Add `src/ui/src/pages/Impact.tsx` with a Lakeview iframe embed (or the official embed SDK if supported on Apps).
  2. Configurable dashboard ID via `VITE_IMPACT_DASHBOARD_ID` (or read from backend `/api/config`).
  3. Fallback: a "View in Databricks" link when embed fails.
- **Test / acceptance.** Dashboard renders in an auth'd browser session; fallback link shown if the user isn't auth'd; unit test for backend `/api/config` endpoint.
- **Blast radius.** One new page + nav entry + tiny backend endpoint.

### T-202 Embed / link the Genie Space
- **Problem.** Genie exists ("Strategist Cockpit Genie") but has no touchpoint in the app.
- **Plan.** Add a "Ask the data" CTA on Home and a route `/ask` that embeds or deep-links the Genie Space. Depends on T-201 approach decision.
- **Test / acceptance.** CTA visible; link resolves to the correct Genie Space; tracked in an integration test if possible.
- **Blast radius.** One new link / page.

### T-203 Bring `docs/` in sync with code
- **Problem.** `docs/architecture.md` still describes the deleted `/impact` page; API doc doesn't mention `view` action on engagements; no mention of `build_dashboard.py` location.
- **Plan.** Do a pass on `architecture.md`, `api-reference.md`, `development.md` after T-201 / T-003 land. Delete the old diagram's `/impact` box or rename it.
- **Test / acceptance.** A fresh read of `docs/` matches the running app and the file tree.
- **Blast radius.** Docs only.

### T-204 Add "Use Case (UCO) links" on engagements
- **Problem.** The idea prompt mentions linking engagements to UCOs (Salesforce). Currently engagements only carry ASQ ID/URL.
- **Plan.** Add `uco_ids` (comma-separated) to `Engagement` + API + UI. Later: query UCO progression metrics via logfood/SFDC.
- **Test / acceptance.** CRUD works with UCO IDs; list view shows them; migration is additive.
- **Blast radius.** Schema (additive), API, UI.

---

## P3 — Future integrations

### T-301 Bridge to `strategist-toolbox` STRIDE agent
- **Problem.** A sibling effort builds STRIDE-based engagement qualification (Level 3 vision: AE/SAs talk to agent before reaching strategist). Cockpit can host or deep-link this.
- **Plan.** Start with a "Qualify new engagement" button on Engagements page that opens the toolbox agent UI (if reachable) or routes to the Slack workflow.
- **Test / acceptance.** Button visible; link resolves; no regression on Engagements page.
- **Blast radius.** One link today; potentially a whole new route later.

### T-302 Production hardening for multi-user
- **Problem.** Today the app is single-user (Felix). Opening to other strategists needs auth-scoped data.
- **Plan.** Introduce `strategist_email` as the tenant key on `Engagement` + `Project` models; filter lists by authenticated user (via OBO or app-level claim); update seeder to accept an email arg.
- **Test / acceptance.** Two users see only their own engagements in tests using mocked identity.
- **Blast radius.** Schema change (non-trivial). Coordinate with the SDR/security review.
