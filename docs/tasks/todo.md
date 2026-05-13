# Strategist Cockpit — Backlog

> Maintained by Claude Code. Each task: **Problem · Plan · Test/Acceptance · Blast radius**. Priorities: **P0** = hygiene, unblocks everything · **P1** = code quality / "make it ours" · **P2** = feature gaps · **P3** = future integrations.
>
> Way of working (same as CLAUDE.md): **Investigate → Plan incl. test design → Implement → Thoroughly test → Iterate.** Focus on operational efficiency, security, and coding best practices.

## Done (2026-05-13 Backlog finisher — Phases A/B/C/D)

Closed out the activity-tables → impact-dashboard backlog in one orchestrated session. Cockpit `main` advanced from `d4c206f` to `cb5057e` (19 commits, both remotes); vibe repo got PR #1411 (Mode E). Dashboard republished to logfood (`01f0f51a424b1cc0bc6f5feba0c33948`); Page 1 is now a 5-pillar summary instead of 6 customer-only tiles.

**Phase A — sequential:**
- **T-216** New activity tables: `evangelism_events`, `initiatives`, `focused_account_planning`, `exec_meetings` + `v_engagement_categories_unified` view. Idempotent DDL appended to `scripts/init_uc_tables.sql`; applied to logfood via MCP. Worker `b4ba0a3`, merge `9086681`.
- **T-217** One-shot Sheet → UC migration script `scripts/migrate_strategist_activity_from_sheet.py` (single file, 1038 lines) + 72 new parser/idempotency/collision tests. Dry-run parses 84/93 rows across 4 tabs. Added `pyarrow` to dev deps; regenerated `requirements-dev.txt`. Worker `af4cc56`, merge `d6edae5`.

**Phase B — 5 parallel workers:**
- **T-219** Evangelism reach dashboard page (3 datasets + 6 panels). Merge `06e2b38`.
- **T-222** Relationship depth dashboard page (3 datasets + 5 panels including Focus×quarter heatmap and CXO-gap actionable table). Merge `a6eeb8a` (spliced).
- **T-213** UCO velocity view `v_customer_engagement_uco_velocity` + 4 panels on Impact Analysis. Joins `asq_uco` directly because T-204's `uco_ids` column was never actually deployed — see T-225 follow-up. Merge `ad29550`.
- **T-212** Activity overlay `activity_app_data` (drops dormant `customer_engagement_app_data`) + 10-tag closed enum + `ImpactTagPicker` UI + 3 dashboard panels + 16 new tests. Merge `6166ac8`.
- **T-218** Mode E in vibe `strategist-systems-hygiene` (renamed from spec's "Mode D" because that name was taken by existing SFDC-backfill flow). Classifier extension + scribble→UC writer via DBSQL `MERGE INTO`. Vibe PR #1411 merged 2026-05-12 17:36Z.

**Phase C — 2 parallel workers:**
- **T-221** Initiative outcomes dashboard page (2 datasets + 5 panels including CXO-sponsorship + stalled-initiatives leading indicator). Merge `7cec6f6`.
- **T-223** Portfolio readiness dashboard page (5 worklist datasets + KPI tiles + detail tables — the Monday-morning page). Discovered `engagement_status` enum is `{New, In Progress, On Hold, Complete, Approved}`; mapped "open" → `(In Progress, New, Approved)`. Merge `f2bba22` (spliced).

**Phase D — sequential capstone:**
- **T-214** Windowed revenue attribution. Constants `ONEOFF_WINDOW_QUARTERS = (1, 4)` and `FOCUS_WINDOW_FYS = (0, 1)` at top of `scripts/build_dashboard.py`. 5 datasets rewritten with CTE chains; new `ds_influenced_revenue_windowed` + KPI tile. Combined drop: $122M → $36.30M (-70%). Old wide-window WHERE clauses preserved in inline comments for rollback. Docs/architecture.md gets new "Impact dashboard semantics" section. Merge `4c5f498`.
- **T-224** Executive Summary v2 capstone — rebuilt Page 1 from 6 customer-only tiles to 5 pillar tile-groups. New `ds_portfolio_pillars` LEFT JOINs all 5 pillar aggregates by `(strategist_email, fy)`. Rollback path preserved via `_OLD_P_EXEC_SUMMARY_LAYOUT_ROLLBACK` module variable. Lakeview canvas widgets don't expose widget-onClick → page-nav, so deep-links are markdown hints in each pillar header. Merge `cb5057e`.

**Cross-cutting follow-ups remaining:**
- **T-225 (new)** — deploy `uco_ids` column on `customer_engagements_manual` properly + project it in `v_customer_engagements_unified`, then simplify T-213's velocity view to use the column instead of joining `asq_uco` directly. Not urgent — the workaround works for SFDC-backed engagements; orphan manuals are dropped. See P2 section below.
- T-217 `--apply` to backfill 84 rows from the Strategist Tracking Sheet — Felix runs after eyeballing `/tmp/migration_2026-05-12.md`.

Verified: `pytest tests/` 201 passed / 7 skipped (was 113 at start of session); `ruff check src tests scripts` clean; `npm run build` clean; dashboard republished cleanly to logfood.

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

## Still open

The stale `## P0 — Hygiene` / `## P1 — Code quality / "make it ours"` / `## P2 — Feature gaps` open lists were retired on 2026-05-13 — every entry that used to live there had already shipped (T-001..T-110 closed 2026-04-24; T-201..T-206 closed 2026-04-29 + 2026-05-04; T-212..T-224 closed 2026-05-13 in the backlog finisher). The detailed Problem/Plan/Test descriptions remain in the relevant "Done" sections above with merge SHAs.

What's actually open going forward:

### T-225 Deploy `uco_ids` column properly + simplify T-213 view (follow-up)
- **Problem.** T-204 (closed 2026-04-24) added `uco_ids` to the app-side schema/repo and the `customer_engagements_manual` DDL block in `scripts/init_uc_tables.sql`, but the column was never actually pushed to the deployed UC table — `DESCRIBE main.field_strategist_cockpit.customer_engagements_manual` doesn't return it, and `v_customer_engagements_unified` doesn't project it. T-213 (closed 2026-05-13) discovered this and worked around it by joining `asq_uco` directly, which means orphan manual engagements (no `asq_id`) drop out of the UCO velocity panels.
- **Plan.**
  1. `ALTER TABLE main.field_strategist_cockpit.customer_engagements_manual ADD COLUMN uco_ids ARRAY<STRING>` on logfood.
  2. Backfill the column for existing manual rows where the strategist remembers UCO membership (probably <10 rows; manual one-shot).
  3. Update `v_customer_engagements` + `v_customer_engagements_unified` to project `uco_ids` (UNION ALL preserves orphan rows; SFDC side reads `uco_ids` via Salesforce custom field if it exists, else NULL).
  4. Simplify `v_customer_engagement_uco_velocity` (T-213 view) to derive UCO membership from the projected `uco_ids` column instead of joining `asq_uco` directly. Orphan manuals with `uco_ids` populated would then surface in the velocity panels.
- **Test / acceptance.** `SELECT uco_ids FROM v_customer_engagements_unified WHERE source='manual' AND uco_ids IS NOT NULL` returns ≥1 row after backfill. Velocity panels show the same numbers as today plus the previously-dropped manual rows.
- **Blast radius.** UC DDL (additive — `ADD COLUMN` is fast) + view rewrite + one-time manual backfill. Low risk; can revert by ignoring the column. Coordinate with T-206 if its `customer_engagements_manual` write path needs to learn the new column.
- **Priority.** Low. The workaround in T-213 captures every SFDC-backed engagement (the bulk of Felix's portfolio); orphan manuals are a small minority. Worth doing for completeness, not urgent.

### T-211 Migrate to autoscaling Lakebase Postgres once GA on Central Logfood (BLOCKED — goal end-state)
- **Status.** Blocked on Lakebase Autoscaling reaching GA on Central Logfood. See full Plan/Test/Blast-radius in the original entry (`git log -p docs/tasks/todo.md` for the pre-2026-05-13 text).

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
