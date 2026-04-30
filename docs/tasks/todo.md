# Strategist Cockpit — Backlog

> Maintained by Claude Code. Each task: **Problem · Plan · Test/Acceptance · Blast radius**. Priorities: **P0** = hygiene, unblocks everything · **P1** = code quality / "make it ours" · **P2** = feature gaps · **P3** = future integrations.
>
> Way of working (same as CLAUDE.md): **Investigate → Plan incl. test design → Implement → Thoroughly test → Iterate.** Focus on operational efficiency, security, and coding best practices.

## Done (2026-04-29 SDR-4682 closure sweep — Tracks A + C)

Landed across multiple commits to close SDR-4682 high-leverage findings:

- **T-209 / F-TM-3 (High)** Path traversal in SPA catch-all replaced with
  `StaticFiles(directory=static_dir, html=True)`. Starlette canonicalises and
  rejects paths that escape the directory. New `tests/test_static_traversal.py`
  drops a sentinel file at the repo root and confirms `/../sentinel`,
  `/..%2fsentinel`, etc. never leak it. `conftest.py` ensures a stub
  `static/index.html` exists so tests exercise the mount.
- **T-210 / F-TM-6 (Medium)** Split `pyproject.toml` into `dependencies`
  (runtime) + `[project.optional-dependencies].dev` (pytest, ruff). Generated
  hash-pinned `requirements.txt` (runtime) + `requirements-dev.txt` (runtime+dev)
  via `uv pip compile --generate-hashes`. CI uses `pip install --require-hashes
  -r requirements-dev.txt`. README, CLAUDE.md, docs/development.md updated.
- **T-207 / F-TM-4 (High)** New `src/backend/auth.py` with
  `current_user_email()` FastAPI dep (reads `X-Forwarded-Email`; dev fallback
  to `dev@local`; 401 in prod when `STRICT_AUTH=1`) + `is_admin()` against
  `ADMIN_EMAILS` env. New `src/backend/audit.py` with `record_event()` emitting
  structured JSON to `strategist_cockpit.audit` logger. Wired into every
  state-changing route — engagements POST/PUT/DELETE, projects POST/DELETE,
  chat POST. Chat logs `prompt_length` only, never content. UC Delta sink
  for these events lands with T-206. Tests cover auth fallback paths, admin
  list overrides, audit JSON shape, and that `extra` can't overwrite canonical
  fields.
- **T-208 / F-TM-5 (Medium)** Added `created_by_email` column to `Project`
  (indexed). POST stamps it from `current_user_email()`. DELETE returns **404**
  (not 403, per reviewer guidance) when caller is neither creator nor admin.
  Two-user mock test in `tests/test_projects.py` proves the gating.
- **F-TM-7 (Low)** Added a "Sync direction (policy)" paragraph to
  `docs/architecture.md` stating Lakebase → UC is the only permitted direction
  for `main.field_strategist_cockpit.engagement_details`.

**Not addressed in this sweep — depend on SDR approval / OBO / Lakebase:**

- **F-TM-1 / T-206** Multi-tenancy column + per-row filter on engagements/projects
  — can only land once schema migration completes (in flight in a separate session)
  and OBO is wired (post-SDR approval).
- **F-TM-2 / T-205** Chat path on OBO — `auth.current_user_email()` is in place,
  but the WorkspaceClient(token=user_token) substitution in `chat.py` still
  needs `X-Forwarded-Access-Token` plumbing. Will land alongside the OBO rollout.

## Done (2026-04-24 sweep)

Landed in commits on `main`:

- **T-001** Split working tree into meaningful commits
- **T-002** Confirmed `strategist_cockpit.db` is not tracked (no-op)
- **T-003** Moved `build_dashboard.py` → `scripts/build_dashboard.py`; fixed unquoted `true`/`false` literals that would have failed Python parsing
- **T-004** Un-tracked `tsconfig.tsbuildinfo`, added `*.tsbuildinfo` to `.gitignore`
- **T-101** Removed `CORSMiddleware`; app is same-origin in both prod and dev
- **T-102** Dropped unused `databricks_token` from `Settings`
- **T-103** Rewrote `chat.py` as thin KA proxy + single offline response; simplified tests
- **T-104** Unique activity IDs per canvas position; router accepts new + legacy slugs; parametrized tests
- **T-105** `seed_database.py` is idempotent by default; `--force` for destructive reseed
- **T-106** Added ruff + eslint + GitHub Actions CI (`.github/workflows/ci.yml`)
- **T-107** `normalize_quarter` helper collapses `FY25-Q1` → `FY25Q1` at seed time
- **T-108** `SecurityHeadersMiddleware` stamps CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy on every response; allow-lists via `CSP_FRAME_SRC` / `CSP_CONNECT_SRC`; full test coverage in `tests/test_security_headers.py`
- **T-109** `Literal` enums for `engagement_type` / `status`, regex on `fy`, http(s) URL check on `asq_url`, `max_length` caps aligned with SQLAlchemy columns, `str_strip_whitespace`, 422 test cases
- **T-110** CSRF posture documented in `docs/architecture.md` — no session cookies, relies on Databricks Apps auth proxy
- **T-203** `docs/architecture.md` synced with current reality (no `/impact` ghost references, describes view/edit/delete/filter actions, points to `scripts/build_dashboard.py`); `docs/api-reference.md` reflects tightened validation and the new `uco_ids` field
- **T-204** `uco_ids` field on engagements — model, schema, API, form field, list/view display, CRUD test

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

### T-108 Add security response headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- **Problem.** SDR questionnaire flags CSP as required. The app sets none of the standard defensive headers today, so we fail the "defense-in-depth" checks and implicitly allow anything the browser would allow by default.
- **Plan.** Add a small FastAPI middleware that stamps these on every response:
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' <KA endpoint host> <dashboard host>; frame-src <dashboard host> <genie host>; object-src 'none'; base-uri 'self'`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  The dashboard/Genie hosts become configurable via env since T-201/T-202 will embed them.
- **Test / acceptance.** New `test_security_headers.py` asserts each header is present and non-empty on `/api/health`. Manual browser devtools check: no CSP violations in console on every page. Running the app in incognito still renders (no third-party cookie dependency).
- **Blast radius.** One middleware file. Reversible. Risk: overly strict CSP may break the dashboard iframe — tune the `frame-src` list together with T-201.

### T-109 Tighten Pydantic input validation on engagement and project schemas
- **Problem.** `EngagementBase`/`ProjectBase` accept any string, any length, for fields like `engagement_type`, `status`, `fy`, `asq_url`, `customer`. Bad client input reaches the DB unchecked.
- **Plan.**
  1. Convert `engagement_type`, `status`, `fy` to `Literal[...]` types matching the app's dropdown options. Normalize `fy` to `^FY\d{2}$` via a validator.
  2. `asq_url`, `related_documents` (when URL-like): validate as `HttpUrl` (Pydantic).
  3. Cap free-text fields with `max_length`: `customer` 255, `engagement_title` 500, `ae` 255, text fields (`actionable_outcome`, `next_steps`, `related_documents`) 4000.
  4. Add `model_config = ConfigDict(str_strip_whitespace=True)` to trim incoming strings.
  5. Mirror the caps in SQLAlchemy `String(n)` where they already differ.
- **Test / acceptance.** New cases in `test_engagements.py`: POST with invalid `engagement_type` returns 422; POST with 2 KB `customer` returns 422; POST with `asq_url = "not a url"` returns 422; valid payloads still succeed.
- **Blast radius.** `schemas.py`, `models.py` (column lengths), tests. Forward-compatible (tightening, not loosening).

### T-110 (meta) CSRF risk note
- **Problem.** Questionnaire asks for CSRF protection. With the app hosted by Databricks Apps behind their auth proxy and no cookie-based auth in our own code, the CSRF attack surface is effectively zero — but we still need to state the control and re-evaluate if we ever introduce session cookies.
- **Plan.** Add a short section to `docs/architecture.md` under "Security": document that the app relies on the Databricks Apps auth proxy (no self-issued session cookies), therefore classic CSRF doesn't apply. If we ever add our own session tokens, require `SameSite=Strict` + a double-submit token.
- **Test / acceptance.** Doc section present and linked from SDR. No code change.
- **Blast radius.** Docs only.

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

### T-205 Switch Databricks calls to OBO (On-Behalf-Of the logged-in user)
- **Problem.** Today the app uses the default SDK credential resolution, which resolves to the Databricks App's service principal. For logfood rollout we committed to OBO so each strategist sees only what they are authorised to see in Unity Catalog.
- **Plan.**
  1. Read the user's access token from the request — Databricks Apps forwards it as `X-Forwarded-Access-Token` (and the email as `X-Forwarded-Email`). Add a FastAPI dependency `current_user_token()` that returns it (and errors 401 if missing in prod, optional in dev).
  2. In `chat.py`, construct `WorkspaceClient(host=settings.databricks_host, token=user_token)` per request instead of using the default client.
  3. For SQL queries (added by T-201 dashboard embed and any Genie integration), use the same user token via the SQL connector.
  4. Record the required OBO scopes in `app.yaml` per Apps docs: `sql`, `dashboards.genie`, `serving.serving-endpoints`, `catalog.tables:read`, `catalogs.schemas:read`. Document in SDR.
  5. Local dev fallback: if the header is absent, fall back to `DATABRICKS_TOKEN` so `npm run dev` still works — but log a warning so it's never confused with prod.
- **Test / acceptance.** New `test_obo.py`: with `X-Forwarded-Access-Token: fake-token` and the WorkspaceClient mocked, assert the mocked constructor received the token. With no header and `ENV=prod`, chat returns 401. Integration test (manual): in logfood, a user without read on a resource gets a proper denied error rather than a blanket 200.
- **Blast radius.** Chat router + new auth dep + app.yaml scopes. No schema change. Must land before T-206.

### T-206 Pivot the data layer from SQLite/SQLAlchemy to UC + DBSQL
- **Problem.** The cockpit currently CRUDs against local SQLite via SQLAlchemy. For logfood we need to (a) read engagements from `main.field_strategist_cockpit.v_engagements_unified` via a SQL warehouse + OBO, and (b) write app-managed state to UC Delta tables (orphan engagements, app-private overlay, projects). Lakebase was the original target store but is **deferred** until available on Central Logfood (see T-211).
- **Plan.**
  1. New `src/backend/dbsql.py` — thin `databricks-sql-connector` wrapper that takes the user's OBO token (from T-205) and returns a contextually-managed cursor. Falls back to `DATABRICKS_TOKEN` in dev so pytest can run without forwarded headers.
  2. Replace `src/backend/database.py` (SQLAlchemy engine) with two backends behind a feature flag (`DATA_BACKEND=sqlite|dbsql`):
     - `dbsql` (target, prod): raw SQL through the warehouse, scoped per-strategist via OBO.
     - `sqlite` (dev fallback): keep the SQLAlchemy path so `npm run dev` and tests stay fast and offline.
  3. Replace `models.py` with a documented schema for the three app-managed UC tables: `engagements_manual`, `engagement_app_data` (overlay), `projects` (gallery). All three include a `strategist_email` column for tenancy.
  4. Rewrite `routers/engagements.py` to read from `v_engagements_unified` and write to `engagements_manual` (orphans) + `engagement_app_data` (overlay).
  5. Rewrite `routers/projects.py` to read/write `projects` directly via DBSQL.
  6. Drop `data/seed_database.py` for prod (UC tables don't need seeding); keep it for the SQLite dev fallback.
  7. Update `scripts/build_dashboard.py` if any dataset URIs need refreshing post-migration.
  8. New tests under `tests/` mock the SQL warehouse client and assert the right SQL is constructed; golden-path integration test in CI when warehouse creds are available.
- **Test / acceptance.** With `DATA_BACKEND=dbsql` and a logfood warehouse, two strategists see disjoint engagement lists; orphan creation lands in `engagements_manual`; dashboard still renders. With `DATA_BACKEND=sqlite`, the existing pytest suite still passes.
- **Blast radius.** Significant: data layer, routers, tests, docs. 1–2 day refactor. Coordinate with T-205 (OBO must land first).

### T-211 Migrate to autoscaling Lakebase Postgres once GA on Central Logfood (GOAL END-STATE)
- **Problem.** The cockpit's app-managed state is currently on UC Delta + DBSQL — a deliberately **interim** choice because Lakebase Autoscaling is not yet GA on Central Logfood. The target end-state is autoscaling Lakebase Postgres for the OLTP write path: scale-to-zero compute, branching, OLTP-grade write latency. UC Delta then becomes the analytic projection only.
- **Plan.** When Lakebase Autoscaling is GA in logfood:
  1. Provision an autoscaling Lakebase instance `field_strategist_cockpit_oltp` in the workspace (configure scale-to-zero + branching).
  2. Mirror the schemas of `engagements_manual`, `engagement_app_data`, `projects` into Postgres.
  3. Cockpit writes flip from DBSQL Delta INSERT → Lakebase Postgres via SQLAlchemy / asyncpg. Reads of `v_engagements_unified` remain on the warehouse (analytics view).
  4. Add a periodic Lakebase → UC reverse-sync job so the analytic projection in UC stays current for dashboards and Genie (per the migration doc's Step 4).
  5. Update SDR + design doc to reintroduce the App-SP credential for Lakebase writes (alongside OBO reads). The original design's hybrid auth model returns.
- **Test / acceptance.** Latency on engagement edits drops to <100ms p99. Reverse-sync job is monitored. SDR re-review (lightweight — the future shape is already declared as goal end-state).
- **Blast radius.** Re-introduces a write store but the API surface stays the same (just swap the backend). Plan as a minor refactor when Lakebase ships.

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
