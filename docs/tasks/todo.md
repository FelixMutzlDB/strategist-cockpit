# Strategist Cockpit — Backlog

> Maintained by Claude Code. Each task: **Problem · Plan · Test/Acceptance · Blast radius**. Priorities: **P0** = hygiene, unblocks everything · **P1** = code quality / "make it ours" · **P2** = feature gaps · **P3** = future integrations.
>
> Way of working (same as CLAUDE.md): **Investigate → Plan incl. test design → Implement → Thoroughly test → Iterate.** Focus on operational efficiency, security, and coding best practices.

## Done (2026-05-12 SDR-4682 round-5 standing-advisory closure)

ProdSec's round-5 final re-review (2026-05-11) cleared SDR-4682 for
deployment — all C/H/M findings closed across rounds 1–4 and a clean
full re-scan found no new ones. Two LOW non-blocking standing
advisories remained, plus one stale docstring. All addressed in this
sweep so the deploying tree carries nothing on the SDR list.

- **[A-1] LOW Lakebase one-way sync — sharpened in `docs/architecture.md`.**
  Goal-end-state section now states explicitly *"Sync is one-way:
  Lakebase → UC only. UC → Lakebase writeback is forbidden — re-confirm
  at T-211 design time per SDR-4682 standing advisory [A-1]."* Also
  notes the structural enforcement today (no `psycopg2`/`asyncpg`
  imports in runtime code; driver isolated to the `[lakebase]` extra
  per N-10).
- **[A-2] LOW Audit Delta sink observability — `docs/deployment.md`
  post-deploy verification step added.** Tail the Apps log stream after
  first deploy, exercise a state-changing route, confirm structured
  `audit ...` lines appear. Then temporarily revoke INSERT on
  `app_audit_log`, repeat, confirm the `Audit Delta sink failed: ...`
  WARN line is visible — proves warehouse-write failures are observable
  so silent Delta-write loss is detectable. Code side already correct
  (`logging.basicConfig(level=logging.INFO)` in
  `src/backend/main.py:12` passes WARN through).
- **Docstring drift in `src/backend/middleware.py` — fixed.** Module
  docstring now reads `X-Frame-Options: DENY` (matches the code at line
  66, which N-8 already moved off `SAMEORIGIN`).
- **`src/backend/audit.py` docstring — already current.** Reviewer's
  follow-up checklist flagged a stale `current_user_token_or_empty()`
  reference, but the function was removed in commit `4262a3b` and the
  docstring already reads `current_user_token()`. No-op; called out
  here so the reviewer can tick the line.

Verified: `ruff check src tests scripts` clean, `pytest tests/` 113
passed / 6 skipped, `npm run build` clean. Doc-only sweep; zero runtime
behaviour change.

## Done (2026-05-04 P2 closure sweep)

Closed in three commits on `main`:

- **T-205 / F-TM-2 (P2, High)** OBO routing for Stratego chat. New
  `current_user_token()` FastAPI dep reads `X-Forwarded-Access-Token`,
  falls back to `DATABRICKS_TOKEN` in dev with a one-shot warning, 401s
  under `STRICT_AUTH=1`. `chat.py` constructs `WorkspaceClient(host,
  token=user_token)` per request. `app.yaml` now declares
  `user_authorization` scopes (`sql`, `serving.serving-endpoints`,
  `dashboards.genie`) and sets `STRICT_AUTH=1` in prod. New tests cover
  header forwarding, dev fallback, strict 401, and a full chat OBO
  round-trip with the SDK mocked. Commit c697186.

- **T-206 / F-TM-1 (P2, High)** Data layer pivot to UC + DBSQL behind
  `DATA_BACKEND=sqlite|dbsql`. New `src/backend/dbsql.py` (databricks-sql
  context-managed cursor + `fetch_all/fetch_one/execute` helpers, always
  parameterised). New `src/backend/repos/{engagements,projects}_repo.py`
  with read filters on `strategist_email` (F-TM-1) and writes that stamp
  the email from `current_user_email()` — caller-supplied identity beats
  payload identity (test asserts spoofing loses). Routers dispatch on the
  flag; SQLite path unchanged so dev/pytest stay fast. Ops-owned DDL in
  `scripts/init_uc_tables.sql`. 14 new tests for SQL/params shape +
  HTTP-level dispatch. Commit 4a3d06d.

- **T-201 + T-202 (P2)** Lakeview dashboard at `/impact`, Genie space at
  `/ask`. New `/api/config` endpoint exposes `databricks_host`,
  `lakeview_dashboard_id`, `genie_space_id`, `data_backend`. New
  `Impact.tsx` and `Ask.tsx` build iframe URLs `/embed/dashboardsv3/<id>`
  and `/embed/genie/<id>` — fallback cards + "Open in Databricks"
  deep-link. Nav extended to 6 entries; Home tile grid grows. CSP test
  confirms workspace host opt-in via `CSP_FRAME_SRC`. Commit cee2117.

- **T-203 (P2)** Docs sync — `architecture.md`, `deployment.md`,
  `development.md`, `api-reference.md` updated to reflect closed items
  (DBSQL backend, OBO, embeds, env var matrix, project tree). New
  `docs/lessons-learned.md` captures design choices + gotchas (Genie
  Beta URL, embed allowlisting, DBSQL paramstyle, IDENTITY round-trip).

**Not closed in this sweep:**
- **T-211** Lakebase migration — still blocked on Autoscaling GA in Central
  Logfood. Goal end-state for app-managed state once it lands.

## Done (2026-05-08 SDR-4682 round-3 closure sweep)

Reviewer's round-3 re-review (comment 8478300) at HEAD `a11a1b4`. Their
findings list missed two items already shipped (N-7, F-TM-4 durability)
and surfaced four new ones; all four landed plus T-220 closed.

- **N-7 (HIGH) canvas leak — already closed in commit `2ab2354`.** Reviewer
  reviewed at `a11a1b4`, missed the canvas filter that landed in `2ab2354`.
- **F-TM-4 audit Delta sink — already closed in commit `beb1d90`.** Same
  reason — landed after the reviewer's snapshot.
- **N-8 (MEDIUM) frame-ancestors / X-Frame-Options — closed.** Middleware
  now stamps `frame-ancestors 'none'` + `X-Frame-Options: DENY`. App is
  never legitimately framed; intentionally no env-var allow-list so a
  future operator can't loosen this without a code change.
- **N-9 (MEDIUM) style-src 'unsafe-inline' — closed.** Split into
  `style-src 'self'` (block-level, strict) + `style-src-attr 'unsafe-inline'`
  (attribute-level, scoped to React's `style={...}` prop). Static iframe
  heights converted from inline `style` to Tailwind arbitrary classes
  (`h-[calc(100vh-220px)] min-h-[600px]`). Only remaining inline `style`
  is the dynamic chart-bar width on `/engagements`, which now uses the
  attribute-level escape hatch only.
- **N-10 (LOW) vestigial psycopg2-binary — closed.** Moved from
  `[project] dependencies` to a new `[project.optional-dependencies].lakebase`
  extra. Hash-pinned `requirements.txt` + `requirements-dev.txt`
  regenerated; runtime image no longer ships psycopg2 until T-211 needs it.
- **N-11 (LOW) / T-220 token-dep regression risk — closed.** Removed
  `current_user_token_or_empty()`. All routers (chat, engagements,
  projects) now use strict `current_user_token`. `.env.example` documents
  that local dev must set `DATABRICKS_TOKEN` (any non-empty string fine
  in SQLite mode; real PAT for DBSQL mode).

## P1 — Code quality / "make it ours" (open)

(Currently empty — T-220 closed in this sweep. Add new P1 items as
they emerge.)

---

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

### T-212 Qualitative impact tags across all activity categories
- **Problem.** The Impact Dashboard is all $DBU and only covers customer engagements — one of three top-level activity categories (T-215/T-216). The strategist's actual leverage — blockers cleared, exec intros, POCs unlocked, competitors displaced, UCO advances, products introduced, roadmap influenced, talks that landed, CXO conversations, teams enabled — is invisible. Without these we under-tell the story to leadership and over-rely on a noisy revenue proxy that ignores 2/3 of the work.
- **Plan.**
  1. **One unified overlay** instead of per-category overlays. Replace the dormant `customer_engagement_app_data` (post-T-215 name) with a new `activity_app_data` table:
     ```
     activity_app_data (
       category         STRING NOT NULL,   -- 'customer'|'evangelism'|'initiative'|'planning'|'exec_meeting'
       activity_key     STRING NOT NULL,   -- 'asq:<id>'|'manual:<id>'|'evangelism:<id>'|'initiative:<id>'|'planning:<id>'|'exec:<id>'
       strategist_email STRING NOT NULL,
       impact_tags      ARRAY<STRING>,
       impact_notes     STRING,
       updated_at       TIMESTAMP,
       PRIMARY KEY (category, activity_key, strategist_email)
     ) USING DELTA;
     ```
     `activity_key` is the only way to keep SFDC ASQs taggable (their row lives in `asq_uco`, which we can't edit). Drop `customer_engagement_app_data` in the same migration — it was never used.
  2. Closed tag enum (10 tags, Pydantic `Literal[...]` + DB-level CHECK via app, since Delta has no CHECK on array elements):
     - `blocker_cleared` (any) — internal or customer-side blocker resolved
     - `exec_intro` (any) — strategist arranged a customer ↔ Databricks exec connection
     - `cxo_engaged` (any) — meaningful CXO conversation happened (auto-tagged from `exec_meetings.is_cxo`, manual override allowed)
     - `poc_unlocked` (customer) — POC started or progressed because of this work
     - `competitor_displaced` (customer) — directly removed/blocked a competitor
     - `uco_advanced` (customer) — UCO stage progressed (also derivable via T-213 join, but manual tag captures attribution narrative)
     - `product_introduced` (customer) — net-new product line landed at this customer
     - `roadmap_influenced` (initiative) — product team accepted a feature request or feedback
     - `evangelism_landed` (evangelism) — a talk visibly converted downstream (opp, UCO, named follow-up)
     - `team_enabled` (evangelism/initiative) — internal community / FE team capability built
  3. **Backend (`src/backend/repos/activity_overlay_repo.py`, NEW)**: `get_tags(category, activity_key, strategist_email)`, `set_tags(category, activity_key, strategist_email, tags, notes)` via `MERGE INTO`. Per-request: every read of a category row LEFT JOINs the overlay; write path stamps `strategist_email` from `current_user_email()`, never from payload (T-206 pattern).
  4. **Pydantic**: `impact_tags: list[Literal[...]] = []` on Update/Out schemas for all 5 categories. Validator rejects unknown tags and duplicates. Category-tag pairs that don't make sense (e.g., `poc_unlocked` on an evangelism event) are allowed at the schema level but flagged with a soft warning in the UI — we don't want the schema to be the policy enforcer.
  5. **UI**: chip multi-select component (`ImpactTagPicker.tsx`, reusable) lives in a new "Outcomes" section on every activity edit dialog. Chips render on the activity row and in the view dialog. Customer Engagements page gets it first; future pages (Evangelism, Initiatives, Exec Meetings) reuse it.
  6. **Dashboard (`scripts/build_dashboard.py`)**: new dataset `ds_activity_impact_tags` that joins `v_engagement_categories_unified` to `activity_app_data` and `LATERAL VIEW explode`s the array. Three new panels:
     - "Outcome mix (all categories)" KPI strip on Page 1 (Portfolio at a glance — see T-224), FY-filtered.
     - "Outcomes by category" 100% stacked bar on Page 1 (which categories contribute which outcomes?).
     - "Top outcomes per Focus account" detail table on Page 2 (Customer Impact).
  7. SQLite mirror for dev parity: a single `activity_overlay` table with the same shape; ORM model + Alembic-free migration in `data/seed_database.py`.
- **Test design.**
  - Unit (Pydantic): unknown tag → 422; duplicate tag → 422; empty list → 200; valid multi-tag → 200; oversize `impact_notes` (>4000 chars) → 422.
  - Repo (mock SQL): `activity_overlay_repo.set_tags()` in `dbsql` mode constructs a `MERGE INTO activity_app_data ... USING ... ON category = ? AND activity_key = ? AND strategist_email = ?` with the caller's email (spoofing test: payload-supplied email is ignored — same pattern as T-206).
  - Repo (mock SQL): cross-tenant read — Alice's tags are not returned to Bob (`WHERE strategist_email = :me` is mandatory).
  - Repo (SQLite): round-trip — set two tags via `set_tags(category="customer", activity_key="asq:123", ...)`, read back, assert order-insensitive equality.
  - HTTP: PUT `/api/engagements/{id}` with `impact_tags=["blocker_cleared","exec_intro"]` → 200 and GET returns them; PUT with `impact_tags=["nope"]` → 422; PUT with `impact_tags=["blocker_cleared","blocker_cleared"]` → 422.
  - HTTP cross-category: PUT `/api/engagements/{id}` and PUT `/api/evangelism/{id}` (when that route exists) write to the *same* overlay table with different `category` values — assert overlay row count grows by 2.
  - UI (manual click-path): open a customer engagement, select two tags + a note, save, reload page, tags render in row + view dialog with chips colour-coded by tag family.
  - Dashboard: run `python scripts/build_dashboard.py` against a seeded warehouse; `ds_activity_impact_tags` returns non-empty rows across ≥2 categories; visual check on all three new panels.
- **Success criteria.**
  - ≥80% of FY26 customer engagements carry ≥1 tag within two weeks of merge.
  - ≥50% of FY26 evangelism events + initiatives carry ≥1 tag once T-219/T-221 surfaces the UI for those categories.
  - "Outcome mix" tile shows non-zero counts per tag, FY-filterable, strategist-filtered, **category-filterable** (the key affordance over a customer-only tag system).
  - One slide in Felix's next portfolio review is replaced by a screenshot of the Outcome mix tile.
- **Blast radius.** Cross-cuts overlay schema (NEW table + drop dormant one), API (touches all 5 category routers, but only one when they ship sequentially), UI (one new shared component), dashboard (3 new panels), SQLite dev mirror. Additive only — no breaking change for callers of existing routes. **Depends on T-215 (renames) and T-216 (new activity tables) having landed** so the overlay's `category` enum maps to real tables. Coordinate with T-211 if Lakebase Autoscaling lands first (overlay lives in the OLTP store).

### T-213 UCO velocity panel
- **Problem.** Engagements carry `uco_ids` since T-204, but the dashboard never joins to UCO state. The strategist's headline job — moving accounts U1→U6 — is the most under-measured outcome we own. Today an engagement that unlocks a U3→U5 jump looks identical to one that did nothing.
- **Plan.**
  1. New view `main.field_strategist_cockpit.v_customer_engagement_uco_velocity` (DDL in `scripts/init_uc_tables.sql`). Explodes `v_customer_engagements_unified.uco_ids`, joins to `main.field_usage_dashboard.asq_uco` on `uco_id`. Returns one row per (engagement_id, uco_id) with: `current_stage` (U1..U6), `previous_stage`, `days_in_current_stage`, `stages_advanced_since_engagement_start`, `stage_advance_within_90d` (boolean), `most_recent_stage_change_date`.
  2. New datasets in `build_dashboard.py`: `ds_uco_velocity_summary` (aggregate) + `ds_uco_velocity_detail` (per-row for the table panel).
  3. New panels on Impact Analysis:
     - KPI tile: % of FY-active engagements with ≥1 stage advance within 90 days.
     - Bar chart: median `days_in_current_stage` per stage (U1..U6) for engaged accounts.
     - Bar chart: count of U3→U4 / U4→U5 / U5→U6 transitions per quarter, advisor portfolio.
     - Detail table: engagement × UCO × current_stage × days_in_stage × advance_within_90d.
  4. View is idempotent (`CREATE OR REPLACE VIEW`). Permissions: grant SELECT on the view to the Apps SP and to `account users`.
- **Test design.**
  - SQL unit (DBSQL integration, skipped without creds): seed a synthetic engagement linked to a synthetic UCO that moves U2→U3 within 60d → assert `stage_advance_within_90d = true`, `stages_advanced_since_engagement_start = 1`.
  - SQL unit: engagement linked to two UCOs (one advancing, one stuck) → view returns two rows; aggregate KPI counts the engagement once (no double-count) — assert via `COUNT(DISTINCT engagement_id)`.
  - SQL unit: engagement with no matching UCO row → view returns nothing (LEFT vs INNER decision: prefer INNER, and surface "engagements without UCO data" as a separate health metric).
  - SQL unit: stage regression (U4→U3) → `stages_advanced_since_engagement_start = -1`, `stage_advance_within_90d = false`.
  - Dashboard build: `python scripts/build_dashboard.py` runs cleanly; all four new panels render with real Felix FY26 data.
- **Success criteria.**
  - Panel returns non-null numbers on Felix's FY26 engagements.
  - Quarterly transition counts (U3→U4 etc.) match a manually-pulled SFDC report within ±2 records (allow for the asq_uco daily-snapshot lag).
  - At least one "stage-advance-within-90d = true" engagement is visible in the detail table on dashboard launch — confirms the join works end-to-end on production data.
- **Blast radius.** One UC view (new, additive) + dashboard datasets/panels. No app/schema change. Depends on T-204 being populated for real engagements (already true) and on `asq_uco` access being granted to the Apps SP / Felix's OBO scope.

### T-214 Windowed revenue attribution
- **Problem.** Today's revenue datasets (`ds_focus_revenue`, `ds_advisor_benchmark`, `ds_accounts_yoy`, `ds_oneoff_impact_summary`, `ds_focus_impact_summary`) join `v_customer_engagements_unified` to `rpt_c360_overview_unpivoted` with only fiscal-year filters (`fiscal_year BETWEEN 2024 AND 2027`). A Focus account engaged in FY26 contributes revenue from FY24/FY25 too, which is tenure not impact. The "Advisor vs Central region" YoY then looks great for reasons that have nothing to do with us.
- **Plan.**
  1. Define attribution windows as named constants at the top of `build_dashboard.py`:
     - `ONEOFF_WINDOW_QUARTERS = (1, 4)` — engagement_quarter +1 .. +4 inclusive.
     - `FOCUS_WINDOW_FYS = (0, 1)` — engagement_FY .. engagement_FY+1 inclusive.
  2. Rewrite the five revenue datasets to derive each engagement's `window_start_quarter` / `window_end_quarter` (one-off) or `window_start_fy` / `window_end_fy` (Focus), then filter `c.usage_date_fiscal_quarter_start` (or `c.fiscal_year`) before any `SUM`/`AVG`.
  3. Add a new "Total influenced revenue (windowed)" KPI tile to Executive Summary — SUM of in-window $DBU across all engaged accounts in the selected FY.
  4. Keep the existing wide-window panels available behind a comment block for one release, so we can compare before/after. Remove after sign-off.
  5. Document the window definitions in `docs/architecture.md` under "Impact dashboard semantics".
- **Test design.**
  - SQL unit (synthetic): one Focus account, engaged in FY26, revenue rows in FY24/FY25/FY26/FY27 — assert the windowed sum equals only FY26 + FY27.
  - SQL unit: one-off engagement in FY26Q2, revenue rows in every quarter from FY25Q1 to FY27Q4 — assert the windowed sum equals exactly FY26Q3 + FY26Q4 + FY27Q1 + FY27Q2.
  - SQL unit: account engaged in *both* a one-off (FY25Q3) and a Focus (FY26) — each engagement's window is independent; total influenced revenue equals the union of in-window quarters, not the sum (no double-counting).
  - SQL unit: engagement with no `account_id` (orphan manual entry) → contributes 0 to influenced revenue, not an error.
  - Regression: existing panel column names unchanged; visual diff on Impact Analysis shows the same chart shapes but smaller absolute numbers.
- **Success criteria.**
  - "Total influenced revenue (windowed)" is materially lower than the previous unbounded number (target: 20–60% lower — proves the window is binding, but not so tight that it zeroes out Focus accounts).
  - "Advisor Focus vs Central region YoY" delta is closer to the regional baseline than before — the chart still tells a story but it's a defensible one.
  - Felix can answer "what revenue can we credibly claim was influenced by my FY26 work?" with one number from the dashboard.
- **Blast radius.** SQL only — five datasets in `build_dashboard.py`. No app code, no schema. Single PR, one dashboard re-publish. Should land *after* T-212 + T-213 so the dashboard tells the full story (qualitative + UCO + windowed $) at once rather than three sequential reframings.

### T-215 Rename `engagements_*` → `customer_engagements_*` across UC + repo
- **Problem.** The cockpit will track three top-level engagement categories: **evangelism**, **initiatives**, and **customer engagements**. The existing UC objects (`engagements_manual`, `engagement_app_data`, `v_engagements`, `v_engagements_unified`) implicitly own the word "engagement" for the customer-engagement category only. Once T-216 lands new tables alongside them, the bare name becomes ambiguous — "engagement" reads as "any of the three" while the schema still means "customer only".
- **Plan.**
  1. UC rename (DDL):
     - `engagements_manual` → `customer_engagements_manual` (table rename)
     - `engagement_app_data` → `customer_engagement_app_data` (table rename)
     - `v_engagements` → `v_customer_engagements` (view re-create with the new name; drop old)
     - `v_engagements_unified` → `v_customer_engagements_unified` (same)
  2. Repo updates: rename references in `scripts/init_uc_tables.sql`, `src/backend/dbsql.py`, `src/backend/repos/engagements_repo.py` (consider renaming module + class to `customer_engagements_repo`), `src/backend/repos/projects_repo.py` (overlay reference), `scripts/build_dashboard.py` (dataset SQL), `docs/architecture.md`, `docs/api-reference.md`, `CLAUDE.md`. Keep the FastAPI route prefix `/api/engagements` as-is (the API surface continues to talk about "engagements" because that's the user-facing word for the customer category in the UI today — only the storage names get clarified).
  3. Vibe-repo coordination (separate PR): update `plugins/strategist-toolbox/skills/strategist-systems-hygiene/SKILL.md` + `resources/recap.py` to point at the new names. Hold this PR until the UC rename lands so Mode C doesn't break.
  4. No backwards-compat shim. Single PR for the repo side, single DDL migration for UC. Land **before** T-216 so the migration script writes against final names.
- **Test / acceptance.**
  - `grep -r 'engagements_manual\|engagement_app_data\|v_engagements' src/ scripts/ docs/` returns zero hits after the rename PR lands.
  - Existing test suite green (`pytest tests/` + `npm run build`).
  - Manual: `databricks sql --warehouse-id 071969b1ec9a91ca -e "SELECT 1 FROM main.field_strategist_cockpit.v_customer_engagements_unified LIMIT 1"` returns a row.
  - Manual: `/engagements` page in the running app still loads, lists, and edits cleanly.
  - Recap.py against the new names produces the same output (run before/after diff on the last weekly recap output).
- **Blast radius.** Cross-cuts UC DDL + 6+ repo files + sibling vibe-repo PR. Single user (Felix) so cutover is coordinated. Must land before T-216.

### T-216 New activity tables: evangelism, initiatives, focused account planning, exec meetings
- **Problem.** Felix tracks four categories of work outside ASQs in a single Google Sheet (gid 877297594 / 2046362034 / 695041730 / 708458245). The data is unjoinable to UC + DBSQL, invisible to the Impact Dashboard, and detached from the Strategist Cockpit app. T-215 clarifies that two of these (evangelism, initiatives) are peer top-level engagement categories, and two (focused account planning, exec meetings) are enrichment dimensions that link to *any* of the three top-level categories.
- **Plan.**
  1. Append DDL to `scripts/init_uc_tables.sql` for four new Delta tables under `main.field_strategist_cockpit.*`:
     - `evangelism_events(id IDENTITY, strategist_email, event_name, event_type, title, event_date, location, fy, quarter, resources, participants, views, comments, status, next_steps, created_at, updated_at)`. `event_type` enum: Keynote|Breakout|Workshop|Podcast|Moderation|Roundtable|Lightning Talk|Other. `status` enum: planned|delivered|cancelled.
     - `initiatives(id IDENTITY, strategist_email, name, feip_ticket, actionable_outcome, resources, status, fy, next_steps, last_activity_at, created_at, updated_at)`. `status` enum: active|on_hold|paused|complete. `feip_ticket` nullable (reserved per the sheet's empty FEIP column).
     - `focused_account_planning(id IDENTITY, strategist_email, customer, account_id, planning_type, actionable_outcome, ae, fy, quarter, session_date, related_documents, asq_id, next_steps, created_at, updated_at)`. `planning_type` enum: Focused|Light. `asq_id` nullable FK → `v_customer_engagements.asq_id`.
     - `exec_meetings(id IDENTITY, strategist_email, customer, account_id, exec_name, exec_title, is_cxo, objective, outcome, meeting_date, asq_id, evangelism_id, initiative_id, context, created_at, updated_at)`. `is_cxo` boolean (from the sheet's CXO TRUE/FALSE column). All three FKs nullable; 0..3 may be set simultaneously.
  2. New view `v_engagement_categories_unified` UNIONing the three top-level categories (`evangelism` | `initiative` | `customer`) with `(category, id, strategist_email, activity_date, title, fy, quarter, status, next_steps)`. Children (planning sessions, exec meetings) surface via counts joined on `(category, id)` in dashboard panels — not lifted into the UNION.
  3. Tenancy: every table carries `strategist_email`; reads filter on it; INSERTs stamp it from the auth dep (T-205 pattern). Same spoofing-test guarantee as T-206.
  4. App layer is **not** built in this task — pure DDL + reverse-view. Cockpit routers/pages land in a follow-up after Mode D (T-218) has produced ~2 weeks of real data and the schema is proven.
- **Test / acceptance.**
  - `databricks sql -e "DESCRIBE main.field_strategist_cockpit.evangelism_events"` (and the other three) shows the columns above with correct types.
  - `databricks sql -e "SELECT * FROM main.field_strategist_cockpit.v_engagement_categories_unified LIMIT 5"` returns rows (empty for the new categories until T-217 lands; non-empty for `customer`).
  - DDL is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`) — re-running `init_uc_tables.sql` is a no-op.
  - Grants: SELECT on all four tables + view to the Apps SP + `account users` (mirror current `customer_engagements_*` grants).
- **Blast radius.** Additive DDL only. One file (`scripts/init_uc_tables.sql`) + one UC migration. No app code, no schema break. Depends on T-215.

### T-217 One-shot migration: Google Sheet → UC activity tables
- **Problem.** The four new tables from T-216 start empty. The historical data lives in the Strategist Tracking Sheet (`1GkqX-xt1pWXsfSwoNFPPcGfgcOfMdccV_6iEZe5IK3U`) with ~50–200 rows per tab. Migration must normalize three different date formats (DD.MM.YYYY German, M/D/YYYY US, "6 June 2024" English), two quarter formats (`FY26Q1` vs bare `Q2`), and parse embedded status markers (`[complete]`, `--- on hold ---`, `#TODO`) out of free-text fields — without touching the sheet (Felix archives it manually after spot-check).
- **Plan.**
  1. New script `scripts/migrate_strategist_activity_from_sheet.py`. Args: `--tab evangelism|initiatives|focused_account_planning|exec_meetings|all`, `--dry-run` (default), `--apply`, `--rejects-path`.
  2. Read each tab via Sheets API (re-use `google_auth.py` token path used by recap.py). Sheet remains read-only.
  3. Parser pipeline per row:
     - Date parser: DD.MM.YYYY → M/D/YYYY → "DD Month YYYY" → "DD Mon YYYY" → ISO, first match wins. Failures → rejects with reason.
     - Quarter normalizer: `FY26Q1` ✓, `FY26-Q1` → `FY26Q1`, bare `Q2` → infer from `FY` + month of date, missing → derive from date alone via Databricks fiscal calendar (FY starts Feb).
     - Status parser (Evangelism): scan `Next Steps` for `[complete]` → `delivered`; else if `event_date >= today` → `planned`, else → `delivered`.
     - Status parser (Initiatives): scan for `--- on hold ---` / `--- paused ---` / `--- complete ---`; else `active`.
     - Boolean parser (Exec Meetings CXO): `TRUE`/`true`/`1` → true, `FALSE`/`false`/`0`/empty → false.
  4. Stage parsed rows as Parquet in `/Volumes/main/field_strategist_cockpit/staging/<table>_<date>.parquet`. Rejects to `/Volumes/.../staging/<table>_rejects_<date>.parquet` with `original_row_json` + `reason` columns.
  5. With `--apply`: `MERGE INTO main.field_strategist_cockpit.<table>` on natural keys:
     - Evangelism: `(strategist_email, event_name, event_date)`
     - Initiatives: `(strategist_email, name)`
     - Focused account planning: `(strategist_email, customer, session_date)`
     - Exec meetings: `(strategist_email, customer, exec_name, meeting_date)`
  6. Diff report at `/tmp/migration_<date>.md`: rows inserted / updated / skipped (already at target) / rejected per table.
  7. Sheet stays untouched. Felix archives tabs manually after reviewing the diff report.
- **Test / acceptance.**
  - `tests/test_migration_parsers.py`:
    - `test_date_parser`: DD.MM.YYYY, M/D/YYYY, "6 June 2024", "17 Sept 2024", garbage → rejects.
    - `test_quarter_normalizer`: `FY26Q1`, `FY26-Q1`, bare `Q2` with FY context, missing → derived.
    - `test_status_marker_evangelism`: `[complete]` → delivered; no marker + past date → delivered; no marker + future date → planned. Edge: "complete the slides" in prose → NOT delivered (literal-token match only).
    - `test_status_marker_initiatives`: `--- on hold ---` → on_hold; mixed-case markers; no marker → active.
    - `test_cxo_parser`: TRUE/true/1 → true; FALSE/false/0/empty → false.
  - `tests/test_migration_idempotency.py`: run `--apply` twice on the same stage Parquet → second run reports 0 inserts/updates.
  - `tests/test_migration_natural_key_collision.py`: two evangelism rows with same `(event_name, event_date)` but different `title` → collision reported, requires `--allow-conflict` to merge.
  - Integration (skipped without creds): run `--dry-run` against the real sheet; assert per-tab row counts within ±2 of `SELECT COUNT(*) FROM the staging parquet`.
- **Blast radius.** New script only. No app code, no schema change beyond T-216. Re-runnable. Sheet is read-only throughout. Depends on T-215 + T-216.

### T-218 Mode D in `strategist-systems-hygiene`: scribble → activity tables
- **Problem.** Once T-217 backfills history, the four new tables go stale unless Felix manually edits them. The hygiene skill (vibe plugin `strategist-toolbox/skills/strategist-systems-hygiene`) already classifies Activity Scribble entries into customer engagements / internal events / internal projects / interviews and produces a weekly recap (Mode C). Today's classifier doesn't yet route entries into the four new tables. Without Mode D, every new event/initiative/planning session/exec meeting requires a manual SQL `INSERT` — which kills the operational efficiency goal.
- **Plan.**
  1. **This task lives in the vibe repo, not strategist-cockpit.** Tracked here for visibility because the UC schema dependency is owned by this repo.
  2. Extend `recap.py`'s classifier with three new outputs:
     - `evangelism` (split out of today's `internal_event`): calendar/scribble keywords keynote, breakout, workshop, podcast, meetup, summit.
     - `account_planning` (new): keywords "account plan", "TAP map", "think big", "coaching session"; or calendar event title customer + planning/coaching keyword.
     - `exec_meeting` (new): calendar event description names a single external exec; or scribble bullet mentions a named exec with a customer.
     - `initiative` (renamed from `internal_project`): unchanged routing; targets `initiatives` table.
     - `customer_engagement` (existing): unchanged.
  3. New Mode D entry point: `python3 recap.py --sync` or natural-language trigger "sync activity to cockpit".
     - Run classifier on scribble entries within the window (default: last 14 days).
     - For each entry, lookup the target table by natural key (T-217 keys).
     - **Exists** → propose `UPDATE next_steps` (prepend new `[Mon DD] ...` line, reverse-chron).
     - **New** → propose `INSERT` with derived fields. Ambiguous fields (event_type, planning_type) prompt for confirmation, never silently guess.
     - **Always show a diff preview**, like Mode A.
     - After confirmation, write via DBSQL `MERGE INTO`. Verify by read-back (mirrors Mode A safeguard against silent failures).
  4. SKILL.md updates: add Mode D section, expand classifier table, document new triggers ("sync activity", "log evangelism", "log exec meeting").
  5. Eval cases in `evals/test-cases/strategist-systems-hygiene.yaml`: one per new classifier output + one ambiguous case that should defer to user confirmation.
- **Test / acceptance.**
  - `test_classifier_routes`: 10 sample scribble lines covering all 5 categories — each routes to expected category; ambiguous ones flagged for confirmation.
  - `test_mode_d_dry_run`: scribble + empty UC tables → produces a preview, writes nothing without explicit confirmation.
  - `test_mode_d_dated_append`: existing initiative row + new scribble entry referencing it → UPDATE prepends a new `[Mon DD]` line, doesn't overwrite existing `next_steps`.
  - `test_mode_d_new_insert`: scribble entry naming a new event → INSERT with derived `(event_name, event_date, event_type)`; prompts for fields it can't derive.
  - `test_mode_d_natural_key_match`: scribble line matches an existing event by `(event_name, event_date)` → routes to UPDATE, not INSERT.
  - Eval: weekly-recap eval still passes after the classifier extension (no regression on existing routing).
  - Manual: run `--sync` on Felix's current scribble for the last 14 days; spot-check 5 proposed updates before confirming.
- **Blast radius.** Cross-repo — lives in `vibe/plugins/strategist-toolbox/`. No code in this repo. Depends on T-215 + T-216 + T-217 having landed. UC writes (vs SF writes) are new for this skill — must reuse the DBSQL pattern from `src/backend/dbsql.py` rather than re-inventing.

### T-219 Dashboard page: Evangelism reach
- **Problem.** Evangelism (keynotes, breakouts, workshops, podcasts, moderation, roundtables) is one of three top-level activity categories but is entirely absent from the Impact Dashboard. Today the only place this data lives is the Google Sheet; once T-217 backfills `evangelism_events` it becomes queryable, but until a page surfaces it, leadership still sees "the strategist did N customer engagements" instead of "the strategist did N customer engagements *and* delivered M talks reaching K people."
- **Plan.**
  1. Three new datasets in `scripts/build_dashboard.py`:
     - `ds_evangelism_summary` — FY × event_type aggregate: `events_delivered`, `events_planned`, `events_cancelled`, `total_views`, `total_attendance`, `total_comments`, `avg_views_per_event` (group by `event_type`, filter on `status`).
     - `ds_evangelism_by_quarter` — quarter × event_type long-form for the stacked bar.
     - `ds_evangelism_top` — top-N events by `views` (configurable; default 10) with `event_name`, `event_date`, `event_type`, `location`, `views`, `attendance`, `comments`.
  2. New dashboard page **"Evangelism reach"** (insert after "Customer Impact", before "Initiatives"). Panels:
     - KPI strip: Events FY (delivered), Total views FY, Total attendance FY, Unique event_types FY, Planned next 30d.
     - Stacked bar: Events per quarter × event_type (Keynote/Breakout/Workshop/Podcast/Moderation/Roundtable/Lightning Talk/Other).
     - Bar chart: Avg views per event_type (which formats actually land).
     - Detail table: Top events FY by views (with delivered/planned/cancelled badge).
     - Side panel: "Status mix" donut (planned / delivered / cancelled), FY-filtered.
     - Leading-indicator tile: "Events planned in next 30 days" (count + list of event_name + event_date), uses today's date as anchor.
- **Test design.**
  - SQL unit (synthetic, DBSQL integration, skipped without creds): seed 5 evangelism rows across 2 quarters, 3 event_types, 2 strategists → `ds_evangelism_summary` returns the expected per-event_type aggregates for the caller's email only (tenancy assertion).
  - SQL unit: row with `status='cancelled'` does not count in `events_delivered`; row with future `event_date` and `status='planned'` counts in "Planned next 30d" only if `event_date <= current_date() + interval 30 days`.
  - SQL unit: `views` NULL → contributes 0 to `total_views` (not `NaN`); `attendance` NULL same.
  - SQL unit: `ds_evangelism_top` ties — same views value across two rows → deterministic ordering by `event_date DESC` then `event_name ASC`.
  - Dashboard build: `python scripts/build_dashboard.py` runs cleanly; all 6 panels render with real backfilled data from T-217.
- **Success criteria.**
  - Total `events_delivered` in FY26 matches the sheet's manually-pulled count ±0 (after T-217 lands).
  - "Avg views per event_type" surfaces at least one non-obvious finding (e.g., podcasts > keynotes for reach per hour invested) — qualitative bar, but the panel must actually *enable* the question.
  - Felix can answer "how much external reach did I drive in FY26?" with one number from Page 3.
  - Leading-indicator tile actually drives action: at least one planned event gets a status-update edit within 7 days of dashboard launch (proves the page is being read).
- **Blast radius.** SQL only — three new datasets in `build_dashboard.py` + one new page block. No app/schema change. **Depends on T-216 (table) + T-217 (data).** Parallelisable with T-221 / T-222.

### T-221 Dashboard page: Initiative outcomes
- **Problem.** Internal initiatives (Field Eng improvement projects, FEIP tickets, product-feedback campaigns) are the second uncounted top-level category. They're where the strategist's *organisational* leverage shows up — but today they live in the Google Sheet, invisible to any dashboard. Once T-217 lands the data, leadership still won't see it unless we wire panels.
- **Plan.**
  1. Two new datasets in `build_dashboard.py`:
     - `ds_initiatives_status` — FY × status aggregate: `active`, `on_hold`, `paused`, `complete`. Plus `last_activity_at` (latest of `updated_at` across child rows in exec_meetings/customer_engagements linked via `initiative_id`).
     - `ds_initiatives_with_links` — initiative-level detail: `name`, `feip_ticket`, `status`, `fy`, `linked_exec_meeting_count`, `linked_customer_engagement_count`, `days_since_last_activity`.
  2. New dashboard page **"Initiative outcomes"**. Panels:
     - KPI strip: Active initiatives, Completed FY, On hold, Stalled (`days_since_last_activity > 30`), FEIP tickets tracked.
     - Stacked bar: Initiatives by status × FY (so you see "complete" growing over time).
     - Detail table: Initiatives FY with `name`, `feip_ticket` (linked if present), `status`, `last_activity_at`, `linked_exec_meeting_count`, `linked_customer_engagement_count`. Sortable by stale-ness.
     - Cross-category panel: "Initiatives with CXO sponsorship" — initiatives where ≥1 linked exec_meeting has `is_cxo=true`. Shows which internal projects are exec-backed.
     - Leading-indicator tile: "Stalled initiatives" (count + list of name + days_since_last_activity), threshold configurable, default 30 days.
- **Test design.**
  - SQL unit (synthetic): seed 4 initiatives — one of each status — verify `ds_initiatives_status` aggregates match. One stalled (last_activity 45d ago), one fresh (5d ago) → stalled tile counts 1, not 2.
  - SQL unit: initiative with 0 linked exec_meetings/customer_engagements → appears in detail table with counts = 0, not NULL.
  - SQL unit: initiative with 2 exec_meetings, one with `is_cxo=true` → appears in "CXO sponsorship" panel; initiative with only `is_cxo=false` linkages does not.
  - SQL unit: `feip_ticket` NULL → renders as "—" in detail table (handled at panel formatting, not view).
  - SQL unit: cross-strategist tenancy — Alice's initiatives don't leak into Bob's aggregates.
  - Dashboard build: 5 panels render; visual diff against last week's snapshot is stable.
- **Success criteria.**
  - "Stalled initiatives" tile flags at least one real initiative on launch and Felix takes action (close/revive/note) within 7 days — proves it's a *useful* leading indicator, not just a chart.
  - "Initiatives with CXO sponsorship" returns ≥1 row by end of FY26 (i.e., the cross-table linkage actually works for real data).
  - One QBR slide is replaced with a screenshot of the Initiatives status stacked bar.
- **Blast radius.** SQL only — 2 datasets + 1 page block. No app/schema change. **Depends on T-216 + T-217 + T-218** (T-218 keeps `last_activity_at` fresh; without it the stalled tile is unreliable). Parallelisable with T-219 / T-222.

### T-222 Dashboard page: Relationship depth (exec meetings)
- **Problem.** The strategist's job at any senior account is *relationship depth* — how many CXOs we engage, how often, across how many accounts. Today this is anecdotal. Once `exec_meetings` (T-216) is populated, depth becomes measurable. Without a page, the data sits inert.
- **Plan.**
  1. Three new datasets:
     - `ds_exec_meetings_summary` — FY aggregate: `meetings_total`, `cxo_meetings`, `distinct_cxos`, `distinct_accounts`, `distinct_accounts_with_cxo`.
     - `ds_exec_meetings_per_account` — account-level: `customer`, `account_id`, `total_meetings`, `cxo_meetings`, `last_meeting_date`, `linked_initiative_count`, `linked_evangelism_count`.
     - `ds_exec_meetings_gap` — accounts with `is_cxo=true` exec meetings in the last 180d but NO customer_engagement in the same window (the "we have the relationship but no work in flight" gap).
  2. New dashboard page **"Relationship depth"**. Panels:
     - KPI strip: Distinct CXOs FY, Distinct accounts with CXO meeting FY, Total exec meetings FY, CXO % (cxo_meetings / total).
     - Heatmap: Exec meetings per Focus account × quarter (rows = Focus accounts, columns = FY26Q1..FY27Q4, cell = meeting count, highlight `is_cxo=true`).
     - Time series: Exec meeting cadence (count per month, separate lines for cxo / non-cxo).
     - Gap panel (detail table): `ds_exec_meetings_gap` rows — "CXO touched, no work in flight." Most actionable panel on the dashboard for QBR prep.
     - Cross-category tile: "Exec meetings tied to an initiative" count — measures whether internal work gets exec air time.
- **Test design.**
  - SQL unit (synthetic): 6 exec_meetings across 3 customers, 2 with `is_cxo=true` at the same customer → `distinct_cxos` = 2 (people), `distinct_accounts_with_cxo` = 1 (account); not double-counted.
  - SQL unit: `ds_exec_meetings_gap` — customer with CXO meeting in last 180d and customer_engagement in last 180d → does NOT appear in gap panel; customer with CXO meeting and no engagement → appears.
  - SQL unit: heatmap — Focus account with 0 exec_meetings appears as a row with all zero cells (not absent — strategist needs to see the gap).
  - SQL unit: `customer_engagement` linkage via `exec_meetings.asq_id` matches when the ASQ is from `asq_uco`; orphan via `manual:<id>` requires a parallel join path — assert both paths populate `linked_customer_engagement_count`.
  - SQL unit: cross-strategist tenancy.
  - Dashboard build: 5 panels render; heatmap legend reads correctly (CXO highlighted).
- **Success criteria.**
  - Gap panel flags ≥3 accounts on launch (assuming Felix's portfolio has the typical CXO-without-engagement pattern). Each flagged account gets an action within 30 days (engagement created OR explicit "no action" annotation).
  - Distinct CXO count matches manual SFDC pull ±1.
  - At least one Focus account in the heatmap shows zero exec meetings for the last 2 quarters → triggers a planning conversation.
- **Blast radius.** SQL only — 3 datasets + 1 page block. **Depends on T-216 + T-217.** Parallelisable with T-219 / T-221.

### T-223 Dashboard page: Portfolio readiness (leading indicators)
- **Problem.** Today's dashboard is 100% lagging — it tells you what happened, not what to do this week. The strategist's most valuable dashboard is one they open every Monday morning and act on. T-219/T-221/T-222 each have one leading-indicator tile, but the highest-density "what to do this week" view needs its own page — and the cross-table joins it requires (engagements ⋈ planning ⋈ exec_meetings ⋈ initiatives) only make sense once all four tables exist.
- **Plan.**
  1. Five new datasets (all return small row counts; the page is a worklist, not analytics):
     - `ds_focus_without_plan` — Focus accounts with no `focused_account_planning` row in the last 90 days. Returns `customer`, `account_id`, `days_since_last_plan`, `ae`, `last_engagement_date`.
     - `ds_focus_without_engagement` — Focus accounts with no customer_engagement in the current quarter. Same shape.
     - `ds_open_asqs_without_next_steps` — Open ASQs (status ∈ Ongoing/Not started) with empty/null `next_steps` for ≥14 days. Tightly bounded — should be ≤10 rows or there's a hygiene problem.
     - `ds_stalled_initiatives` — Initiatives with `last_activity_at` > 30 days ago and `status='active'`.
     - `ds_oneoff_without_followup` — One-off engagements completed >90 days ago with no subsequent engagement or planning session at the same account.
  2. New dashboard page **"Portfolio readiness"** (the "Monday morning" page). Panels:
     - 5 KPI tiles, one per dataset, each showing the count + clicking opens the detail table beneath.
     - 5 detail tables (one per dataset) below the tiles — Felix can scan all of them in under 2 minutes.
     - Banner across the top: "Last refreshed: {timestamp}" — so it's obvious if the dashboard is showing stale data.
- **Test design.**
  - SQL unit (synthetic): Focus account with planning row 30d ago → does NOT appear in `ds_focus_without_plan`; 95d ago → appears.
  - SQL unit: Light account with no planning → does NOT appear (panel is Focus-only).
  - SQL unit: `ds_open_asqs_without_next_steps` — ASQ with `next_steps` containing only whitespace → counts as empty; with real text → does not appear.
  - SQL unit: `ds_stalled_initiatives` — initiative with `status='on_hold'` and no activity for 60d → does NOT appear (on_hold is intentional, not stalled).
  - SQL unit: `ds_oneoff_without_followup` — one-off completed 100d ago, followed by a Focus engagement at the same account → does NOT appear (any follow-up activity counts).
  - SQL unit: edge — Focus account that's brand new (created <90d ago) and has no planning yet — currently appears. Decision: keep it; brand-new Focus *needs* a plan. Add `MIN(days_since_engagement_created, 90)` to the panel as a soft signal.
  - Dashboard build: page loads in <3s (worklist must be snappy or it won't get checked weekly).
- **Success criteria.**
  - Felix opens this page ≥4 times in the first 14 days post-launch (instrument via Lakeview audit log query if available; otherwise self-report).
  - ≥50% of items flagged in the first week get resolved or annotated within 14 days (the page must drive action, not just decoration).
  - At least one item caught here saves a renewal conversation or surfaces a blocker before it becomes a problem — measured at end of FY26 retro.
  - The page becomes the highest-traffic dashboard page within 30 days of launch.
- **Blast radius.** SQL only — 5 datasets + 1 page block. **Depends on T-216 + T-217 + T-218 + T-204 (uco_ids).** Highest signal/effort ratio of the new pages — recommended priority right after T-212 lands.

### T-224 Executive Summary v2: one tile per pillar
- **Problem.** Today's "Executive Summary" page is six activity tiles for the customer category only (Total Accounts, Focus Accounts, One-off Engagements, Territories, AE Partners, Total Engagements). After T-219/T-221/T-222/T-223 land, the dashboard tells five stories — but the front page still tells one. Anyone (skip-level, peer strategist, exec sponsor) who opens the dashboard sees a misleadingly narrow summary that under-represents the strategist's portfolio by ~2/3.
- **Plan.**
  1. Rebuild the front page as five pillars, one tile-group per pillar, FY-filterable and strategist-filterable. The page should answer "what kind of strategist am I, and how am I doing this year" in under 30 seconds:
     - **Customer impact**: Total influenced revenue (windowed — T-214), UCO advances FY (T-213), tagged outcomes count (T-212).
     - **Evangelism reach**: Events delivered FY, Total reach (views + attendance), Planned next 30d.
     - **Initiative outcomes**: Active initiatives, Completed FY, CXO-sponsored count.
     - **Relationship depth**: Distinct CXOs FY, Accounts with CXO meeting FY, CXO meetings without follow-up engagement (gap).
     - **Portfolio readiness**: Focus accounts without plan, Open ASQs needing attention, Stalled initiatives (sum of T-223 worklist counts).
  2. Each tile-group is 3 KPIs + a sparkline (FY trend). Tile-group clicks deep-link to the corresponding pillar page (Page 2..6).
  3. New dataset `ds_portfolio_pillars` that left-joins all five pillar aggregates by `(strategist_email, fy)`. Single query, not 5 — so the page loads as one widget.
  4. Land **after** T-219/T-221/T-222/T-223 — needs the per-pillar datasets to exist so we don't duplicate aggregation logic.
- **Test design.**
  - SQL unit: `ds_portfolio_pillars` returns one row per (strategist_email, fy) with all 15 KPIs as columns. NULL handling: strategist with no evangelism rows still gets a row with `evangelism_count = 0`, not absent.
  - SQL unit: deep-link URLs in tile-group config resolve to the right pillar page IDs.
  - Visual: sparkline trends match the per-pillar page's headline number when filtered to the same FY.
  - Manual: open Page 1, eyeball each KPI, click into the corresponding pillar page — assert the deep-linked page shows the same headline number.
- **Success criteria.**
  - Page 1 is the only page an exec needs to see — i.e., a non-strategist viewer can describe Felix's FY26 portfolio after 30 seconds on Page 1.
  - The new tiles surface ≥2 narratives that the old Executive Summary hid (typical candidates: evangelism reach exceeds customer engagement count; relationship gap panel highlights a CXO-rich account with no active work).
  - Felix replaces ≥3 hand-built portfolio slides with screenshots from Page 1.
- **Blast radius.** SQL + dashboard layout — 1 new dataset + Page 1 rebuild. **Depends on T-219 + T-221 + T-222 + T-223** (and ideally T-212/T-213/T-214 for the customer-pillar tiles to be honest). The capstone task; ships last.

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
  2. Mirror the schemas of `customer_engagements_manual`, `customer_engagement_app_data`, `projects` into Postgres.
  3. Cockpit writes flip from DBSQL Delta INSERT → Lakebase Postgres via SQLAlchemy / asyncpg. Reads of `v_customer_engagements_unified` remain on the warehouse (analytics view).
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
