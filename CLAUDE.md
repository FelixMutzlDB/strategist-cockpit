# Strategist Cockpit — Claude Context

> Last updated: 2026-04-23
> Owner: Felix Mutzl (felix.mutzl@databricks.com), Data & AI Strategist, DACH
> Remote: https://github.com/FelixMutzlDB/strategist-cockpit (main only; still on initial commit)
> Target workspace: `adb-2548836972759138.18.azuredatabricks.net` (field-eng)
> Target Databricks App: `strategist-cockpit` (serves SPA from `static/` via FastAPI)

## What this is
A Databricks App for a single Data & AI Strategist to track their portfolio of engagements (ASQs + multi-quarter "Focus" advisory), navigate the Strategist Canvas framework, surface an AI/BI Impact Dashboard, and keep a gallery of reusable assets. Floating "Stratego" chatbot is wired to a Databricks Knowledge Assistant (with a keyword fallback).

Source of truth for intent: [Vibing Dev Scribble → Strategist Cockpit tab](https://docs.google.com/document/d/1dpzA3kJIRBArS92Shp8-X6Se9YbWv78ospi-aybRgOQ/edit?tab=t.9kpatqkpbwru). Sibling effort: the `strategist-toolbox` tab in the same doc (STRIDE qualification, "talk to my agent first" Slack vision).

## Current state
- Pages shipped: Home, Canvas, Engagements (merged former `/impact` + data-entry), Gallery. `StrategoChat` floats on all pages.
- Engagements: full CRUD, global search + FY/type/status dropdowns + per-column filters + sort + view/edit/delete actions, KPI tiles, quarter bar chart.
- Canvas: 5 archetypes (Organizer/Builder/Product/Industry/Advisor) link to slide deck; Goal block lists #1 AI/BI Genie, #2 Lakebase. Clicking a box → keyword-matched summary dialog.
- AI/BI Dashboard: built via `build_dashboard.py` (5 pages: Executive / Focus / One-off / Impact / Filters) — lives in Databricks, **not yet embedded in the app**.
- Genie Space: "Strategist Cockpit Genie" exists in workspace — **not yet embedded in the app**.
- Tests: `tests/` has unit tests for engagements, projects, canvas, chat, health + integration tests for SQL warehouse / KA endpoint / dashboard / Genie (skipped without creds).
- Git: one initial commit. **Almost all real work is still uncommitted** in the working tree (see `git status`). The whole `docs/`, `tests/`, `build_dashboard.py`, `Engagements.tsx` etc. are untracked.
- Built by Cursor originally; we're shifting ownership to Claude Code.

## Read order
- New to the project? Read this file, then `docs/architecture.md`, then `src/backend/main.py` and `src/ui/src/App.tsx`.
- Touching data/dashboard? Read `build_dashboard.py` and the view definitions in Databricks.
- Touching the chatbot? Read `src/backend/routers/chat.py` and `data/stratego_context.md`.
- **Open work lives in `docs/tasks/todo.md`** — consult the backlog before starting new work, and update it when tasks finish or shift.

## Working mode (apply to every non-trivial change)
1. **Investigate.** Read the relevant code, data model, and prior decisions in `docs/` and `CLAUDE.md` before proposing anything. Understand the problem before touching code.
2. **Plan incl. test design.** State the approach *and* how you'll verify it — unit tests, integration tests, manual UI checks. Call out the golden path plus the edge cases. For UI work, spell out which click-paths you'll exercise.
3. **Implement** the smallest safe increment. Commit in meaningful chunks, not one megacommit.
4. **Thoroughly test.** Run `pytest tests/`, `npm run build`, and exercise the UI in a browser. Check console + network + server logs. Type checks and test suites verify code correctness, not feature correctness — if you can't test the UI, say so explicitly instead of claiming success.
5. **Iterate** until the change works end-to-end. Don't declare victory on a partially working feature.

Throughout, prioritise (in this order):
- **Operational efficiency.** Don't overbuild. A bug fix doesn't need surrounding cleanup; a one-shot operation doesn't need a helper. Three similar lines beats a premature abstraction.
- **Security.** No hardcoded tokens, no loose CORS, no string-concatenated SQL, no `dangerouslySetInnerHTML`. Treat the SDR questionnaire as a live checklist (see `docs/deployment.md`).
- **Coding best practices.** Typed boundaries (Pydantic, TS), small focused functions, honest names, no dead code, no backwards-compat shims for code nobody depends on.

## Quick start
```bash
# Backend (SQLite by default)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m data.seed_database
uvicorn src.backend.main:app --reload --port 8000

# Frontend (dev server at :5173, proxies /api → :8000)
cd src/ui && npm install && npm run dev

# Build for deploy (emits to ../../static)
cd src/ui && npm run build

# Deploy to Databricks Apps
databricks apps deploy strategist-cockpit --source-code-path .
```

## Architecture (10-sec version)
- FastAPI (`src/backend/main.py`) → SQLAlchemy → SQLite in dev, Lakebase Postgres in prod (via `DATABASE_URL`).
- Routers under `src/backend/routers/`: `engagements`, `projects`, `canvas`, `chat`. All mounted at `/api/*`.
- React 18 + Vite + shadcn/ui + Tailwind. shadcn primitives under `src/ui/src/components/ui/`, custom in `components/`, pages in `pages/`.
- FastAPI serves the built SPA from `static/` at the root; `/api/*` wins before the SPA catch-all.
- Stratego chat calls `w.serving_endpoints.query(STRATEGO_ENDPOINT_NAME, ...)` via `databricks-sdk`; falls back to keyword answers when the endpoint is unset or fails.

## Key files
| File | Purpose |
|---|---|
| `src/backend/main.py` | FastAPI app, CORS, static mount, SPA fallback |
| `src/backend/config.py` | `Settings` via pydantic-settings, reads `.env` |
| `src/backend/models.py` | `Engagement`, `Project` ORM models |
| `src/backend/routers/engagements.py` | CRUD + filter query params |
| `src/backend/routers/canvas.py` | `CANVAS_ACTIVITY_KEYWORDS` keyword map → summaries |
| `src/backend/routers/chat.py` | KA proxy + keyword fallback |
| `src/ui/src/App.tsx` | Nav, routes, chat mount |
| `src/ui/src/components/StrategistCanvas.tsx` | The canvas layout + archetype links |
| `src/ui/src/pages/Engagements.tsx` | The big page — KPIs, chart, filtered table, view/edit/delete dialogs |
| `data/seed_database.py` | Reads `data/engagements.csv` → inserts Engagements + default Projects |
| `build_dashboard.py` | Builds the Lakeview "Strategist Impact Dashboard (Felix)" (2100 lines) |
| `app.yaml` | Databricks Apps runtime command + env |
| `upload_to_workspace.sh` | Alt deploy path — uploads folders via `databricks workspace import_dir` |

## Unity Catalog assets the app depends on
- `home_felix_mutzl.strategist_canvas.engagement_details` (Delta, from CSV)
- `home_felix_mutzl.strategist_canvas.v_engagements_unified` (joins engagements + ASQ + accounts + revenue)
- `home_felix_mutzl.strategist_canvas.engagements` (pre-existing strategist→accounts mapping)
- `main.gtm_gold.rpt_c360_overview_unpivoted` (revenue per account per period)

## Conventions
- Python: FastAPI routers return pydantic models, not raw dicts. Filter params are always `Optional[str] = Query(None)`. Partial updates use `model_dump(exclude_unset=True)`.
- React: pages own their own data fetching (no global store). Filters + sort live in page-local `useState`. Dialogs are shadcn `Dialog`. New shadcn primitives: `npx shadcn@latest add <name>` from `src/ui`.
- Canvas IDs are string slugs keyed in `CANVAS_ACTIVITY_KEYWORDS`. If you add a new box, add keywords too or it will return 0 matches.
- FY runs **February → January**. FY26 = Feb 2025 – Jan 2026. Use this when interpreting dates.
- Fiscal quarters format: `FY26Q1` (no dash). Source data has both `FY25-Q1` and `FY25Q1` — normalize on read.
- Engagement types live in one place: `ENGAGEMENT_TYPES` in `Engagements.tsx` + `engagement_type` string column. Keep both in sync.

## Known stubs / rough edges (don't build on these, fix them)
- `CORSMiddleware(allow_origins=["*"])` in `main.py` — fine for dev, should be tightened before anyone else uses the app.
- `config.databricks_token` is unused — the SDK auto-reads `DATABRICKS_TOKEN`. Removing it reduces confusion but hasn't happened yet.
- `seed_database.py` does `DELETE FROM engagements` before inserting, so running it wipes manual edits. Needs idempotency before becoming a scheduled job.
- Canvas `events`, `market-scouting`, `community-seeding` IDs appear in two positions. React keys are still OK, but a click on either instance shows identical results — intentional today, deep-linkable tomorrow.
- `chat.py` fallback ladder is long static `if/elif` prose generated by Cursor. Functional, but replace with a single system prompt + KA as soon as the endpoint is stable.
- `strategist_cockpit.db` (SQLite dev DB) is tracked in git despite `*.db` in `.gitignore`. It was committed in the initial commit before the ignore took effect — should be `git rm --cached`'d.
- `build_dashboard.py` sits at the repo root (2100 lines). Logically it's a `scripts/` one-shot, not application code.
- `/impact` page was deleted and rolled into `/engagements`. Any remaining references in docs (`architecture.md`, old screenshots) are historical.

## Don't do (and why)
- **Don't deploy from an uncommitted tree.** Work is effectively unversioned today — commit in meaningful chunks before adding new features.
- **Don't swap SQLite for Postgres locally** just to mirror prod. SQLite + seed is the faster devloop; Lakebase is only exercised via `DATABASE_URL` in Databricks Apps.
- **Don't hand-roll a second CRUD page.** `Engagements.tsx` is the reference: filter bar → KPI cards → chart → table with per-column filters + sort → view/edit/delete/add dialogs. Copy the pattern.
- **Don't hardcode secrets.** `DATABRICKS_WAREHOUSE_ID` is an ID (not secret) — fine to default. Tokens and KA endpoint names come from env / `valueFrom` in `app.yaml`.
- **Don't build a separate "Data Entry" page.** It was intentionally merged into `/engagements` on 2026-02-22 per the idea prompt.

## Future integrations to keep in mind (not built yet)
- Embed the AI/BI Impact Dashboard in a new `/impact` route (iframe or Lakeview embed SDK) — the backing dashboard already exists via `build_dashboard.py`.
- Embed the Genie Space similarly, or expose natural-language queries through Stratego.
- Hook into the `strategist-toolbox` plugin (STRIDE engagement qualification) — same strategist audience; eventually Cockpit could link into or host the toolbox agent.

## Conversational style for this project
- Felix is a Databricks strategist, not a full-time engineer — keep explanations concrete and business-aware, show diffs/commands rather than long prose.
- Prefer small, reviewable changes over rewrites. This codebase came out of Cursor; trust-but-verify when refactoring Cursor-style code (long static `if/elif` chains, duplicated helpers).
- When proposing changes, call out the blast radius (local file, whole page, DB migration, Databricks asset).
