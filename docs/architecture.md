# Architecture

## Overview

Strategist Cockpit is a full-stack Databricks App with a FastAPI backend and React frontend. It integrates with Databricks Unity Catalog, AI/BI Dashboards, Genie Spaces, and Model Serving endpoints.

```
┌──────────────────────────────────────────────────────────────────┐
│                       Browser (React)                            │
│  Home  │  Canvas  │  Engagements  │  Impact  │  Ask  │  Gallery  │
│                       + Stratego Chat                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │ /api/*  +  iframes /embed/dashboardsv3, /embed/genie
┌────────────────────────▼─────────────────────────────────────────┐
│                  FastAPI Backend (uvicorn)                       │
│  routers: engagements, projects, canvas, chat, config            │
│  repos: engagements_repo, projects_repo (DBSQL path)             │
│  auth: current_user_email + current_user_token (OBO)             │
│  SecurityHeadersMiddleware (CSP, X-Frame-Options …)              │
└───┬────────────┬─────────────────┬─────────────────┬─────────────┘
    │ DATA_      │ DATA_           │                 │
    │ BACKEND=   │ BACKEND=        │ /embed/...      │ /serving-endpoints/
    │ sqlite     │ dbsql           │ via iframe      │ (OBO)
    ▼            ▼                 ▼                 ▼
  SQLite     ┌──────────────┐  ┌──────────────┐  Stratego KA
  (dev)      │ Databricks   │  │  Databricks  │  (Model Serving)
             │ SQL warehouse│  │  AI/BI Dash. │
             │ + UC Delta   │  │  + Genie     │
             └──────┬───────┘  └──────────────┘
                    │
          ┌─────────┼─────────────┐
          ▼         ▼             ▼
   v_engagements  engagements_  rpt_c360_
   _unified      manual +       overview_
                 engagement_    unpivoted
                 app_data +
                 projects
```

## Backend

- **Framework**: FastAPI 0.115+
- **Validation**: Pydantic 2.10+ / pydantic-settings
- **Data layer (interim — production):** Unity Catalog Delta tables under `main.field_strategist_cockpit.*`, accessed via Databricks SQL warehouse + the `databricks-sql-connector`, scoped to the logged-in user via OBO (`X-Forwarded-Access-Token`). Selected by `DATA_BACKEND=dbsql`. Closed under T-206.
- **Data layer (goal end-state):** Autoscaling Lakebase Postgres for app-managed state — scale-to-zero compute, branching, OLTP-grade write latency. Will replace the UC Delta write path as soon as Lakebase Autoscaling is GA on Central Logfood. UC Delta retained as the analytic projection. Tracked as T-211.
- **Data layer (dev / pytest):** SQLAlchemy 2 + SQLite. Selected by `DATA_BACKEND=sqlite` (the default). Same router code, branched in two places.
- **Entry point**: `src/backend/main.py`
- **Auth**: `src/backend/auth.py` exposes `current_user_email()` (from `X-Forwarded-Email`) and `current_user_token()` (from `X-Forwarded-Access-Token`). Both have dev fallbacks; `STRICT_AUTH=1` makes missing headers a hard 401.
- **Security middleware**: `src/backend/middleware.py` stamps CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy on every response.

### API Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `engagements` | `/api/engagements` | CRUD with query filtering (fy, engagement_type, status, customer) |
| `projects` | `/api/projects` | CRUD for gallery project items |
| `canvas` | `/api/canvas` | Keyword-matched canvas activity summaries |
| `chat` | `/api/chat` | Stratego chatbot — KA proxy via `WorkspaceClient(token=user_token)` per-request OBO. Offline fallback when `STRATEGO_ENDPOINT_NAME` is unset. |
| `config` | `/api/config` | Public runtime config: workspace host, dashboard ID, Genie space ID, active data backend. Consumed by Impact/Ask pages on load. |

### Data layer dispatch

Each router has two paths, gated by `settings.data_backend`:

- **`sqlite`** (dev): SQLAlchemy ORM via `database.py` + `models.py`. `Engagement` and `Project` tables created in-process by SQLite. Tenancy not enforced (single-user dev).
- **`dbsql`** (prod): repository functions in `src/backend/repos/` open a `databricks-sql` connection authorized with `current_user_token()` and execute parameterised SQL against `v_engagements_unified` (read), `engagements_manual` (orphan writes), `engagement_app_data` (overlay), and `projects` (gallery). Every SELECT carries `WHERE strategist_email = :email`; every INSERT stamps that column from the auth dep, never from payload. DDL for these tables is in `scripts/init_uc_tables.sql` and is owned by ops, not the app.

## Frontend

- **Framework**: React 18 + TypeScript + Vite
- **UI Library**: shadcn/ui (Radix primitives + Tailwind CSS)
- **Routing**: React Router DOM v6
- **Build output**: `static/` directory served by FastAPI

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Home | `/` | Welcome from Stratego + navigation tiles |
| Canvas | `/canvas` | Interactive strategist canvas with dialog summaries per activity |
| Engagements | `/engagements` | KPIs, quarter chart, filter bar (global search + FY + type + status dropdowns), sortable table with per-column filters, CRUD with view/edit/delete actions. |
| Impact | `/impact` | Embedded Lakeview "Strategist Impact Dashboard" — iframe to `https://<host>/embed/dashboardsv3/<id>`, deep-link to the dashboard in Databricks (T-201). |
| Ask | `/ask` | Embedded "Strategist Cockpit Genie" — iframe to `https://<host>/embed/genie/<id>` (T-202). |
| Gallery | `/gallery` | Project thumbnail tiles with add/delete |

### Key Components

- `StrategistCanvas` — Interactive canvas with clickable activity boxes, goal sidebar, and 5 archetype links (Organizer, Builder, Product, Industry, Advisor). Each clickable box has a unique activity slug even when the same label appears in multiple positions.
- `StrategoChat` — Floating chat widget backed by `/api/chat`.

## Databricks Integration

### Unity Catalog Assets

Read sources:

| Asset | Type | Description |
|-------|------|-------------|
| `main.field_strategist_cockpit.v_engagements_unified` | View | Engagements joined with revenue + AE + territory; primary read surface for the cockpit |
| `main.field_strategist_cockpit.v_engagements` | View | UNION of SFDC ASQs (from `asq_uco` daily snapshot) + manual orphans |
| `main.field_strategist_cockpit.engagements_manual` | Delta Table | Canonical store for orphan engagements (no SFDC counterpart). Append-only from the cockpit. |
| `main.field_usage_dashboard.asq_uco` | Delta Table (read-only, owned by Field Usage Dashboard team) | Daily Salesforce ASQ snapshot — upstream input to `v_engagements` |
| `main.gtm_gold.rpt_c360_overview_unpivoted` | Table | Revenue/consumption metrics by account and period |

App-managed write targets (interim — created on first deploy; migrate to Lakebase Autoscaling per T-211 once GA):

| Asset | Type | Description |
|-------|------|-------------|
| `main.field_strategist_cockpit.engagements_manual` | Delta Table | INSERT for new orphan engagements (existing schema; the cockpit becomes the second writer alongside notebook/SQL) |
| `main.field_strategist_cockpit.engagement_app_data` | Delta Table (NEW) | App-private overlay: `next_steps`, `related_documents`, `actionable_outcome`, custom tags. Joined to engagements by `asq_id` (or `manual_id` for orphans). Owner column `strategist_email` for tenancy. |
| `main.field_strategist_cockpit.projects` | Delta Table (NEW) | Gallery items (formerly the Lakebase `project` table). Includes `created_by_email` for ownership-gated DELETE (T-208). |

> Historical note: read sources previously lived under `home_felix_mutzl.strategist_canvas.*`. The migration to `main.field_strategist_cockpit.*` was completed 2026-04-29 (see `~/Library/CloudStorage/GoogleDrive-felix.mutzl@databricks.com/My Drive/Docs Felix/Databricks/2 Ongoing/Strategist Cockpit Migration.md`). The cockpit's local SQLite path is being retired in favour of UC + DBSQL — tracked as T-206.

**Sync direction.** Salesforce is the system of record for ASQs. SFDC writes flow into `main.field_usage_dashboard.asq_uco` via a daily snapshot (~24h lag), which feeds `v_engagements`. The cockpit edits **never write back to SFDC directly** — for SFDC-owned fields, edits go through the `strategist_systems_hygiene` skill in the `strategist-toolbox` plugin (which calls SFDC REST). All other edits live in app-managed UC tables (`engagements_manual`, `engagement_app_data`, `projects`).

### Goal end-state: Autoscaling Lakebase Postgres

The current UC Delta + DBSQL write path is **interim**. The target end-state for app-managed state is **autoscaling Lakebase Postgres** — Databricks-native managed Postgres with scale-to-zero compute, branching, and OLTP-grade write latency. The cockpit will migrate to Lakebase Autoscaling as soon as it is GA on Central Logfood (currently it is not).

Migration shape when Lakebase Autoscaling lands:
- App-managed Delta tables (`engagement_app_data`, `projects`, optionally `engagements_manual`) move to Lakebase for OLTP-grade writes
- Reads of `v_engagements_unified` and `asq_uco` stay on the warehouse (UC remains the analytic projection)
- A periodic Lakebase → UC reverse-sync feeds the analytic projection so dashboards and Genie keep working
- Sync is **one-way: Lakebase → UC only**. UC → Lakebase writeback is forbidden — re-confirm at T-211 design time per SDR-4682 standing advisory [A-1]. Today this is enforced structurally: no `psycopg2`/`asyncpg` import in runtime code; the driver lives behind the `[lakebase]` extra in `pyproject.toml` (N-10 closure)
- App auth flips back to a hybrid: App-SP for Lakebase writes + OBO for UC reads (matches the original design intent)

Tracked as backlog item T-211.

### AI/BI Dashboard

The "Strategist Impact Dashboard" is defined in `scripts/build_dashboard.py` (Lakeview REST). Five pages: Executive Summary, Focus Engagements, One-off Engagements, Impact Analysis, Global Filters. Embedded in the app at `/impact` (T-201, closed) — see "Pages".

**Embed prerequisite:** a workspace admin must allowlist the app's host under **Settings → Security → External access → Embed dashboards** before the iframe will render. The CSP `frame-src` host is also configured via the `CSP_FRAME_SRC` env var (set to the workspace host, space-separated if multiple).

### Genie Space

"Strategist Cockpit Genie" provides natural language queries over the unified engagement view and revenue data. Embedded in the app at `/ask` (T-202, closed). Same workspace allowlisting prerequisite as the dashboard. Genie iframe embedding is currently in Beta — check the `/embed/genie/<id>` URL pattern matches your workspace's release.

### Stratego Chat (Knowledge Assistant)

When `STRATEGO_ENDPOINT_NAME` is configured, `/api/chat` proxies messages to a Databricks Knowledge Assistant via `databricks-sdk`. The `WorkspaceClient` is constructed **per-request** with the user's OBO access token (T-205, closed) — the call is authorized as the strategist, not the app SP. When the endpoint is not configured (local dev), the router returns a single short offline message.

## Security

### Response headers

`SecurityHeadersMiddleware` stamps these on every response:

| Header | Value | Purpose |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' $CSP_CONNECT_SRC; frame-src 'none' \| $CSP_FRAME_SRC; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'` | Defense-in-depth against injection |
| `X-Frame-Options` | `SAMEORIGIN` | Block off-origin iframing of the app |
| `X-Content-Type-Options` | `nosniff` | Disable MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Don't leak request paths cross-origin |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Revoke hardware capabilities the app doesn't need |

Dashboard or Genie iframe hosts are injected via `CSP_FRAME_SRC` (space-separated). Additional outbound call hosts (e.g. the Stratego KA endpoint) go in `CSP_CONNECT_SRC`.

### CORS

There is no CORS middleware. In production the app is served same-origin by Databricks Apps. In local dev the Vite dev server at `:5173` proxies `/api/*` to the backend at `:8000`, so requests are also same-origin from the browser's perspective.

### CSRF

The app issues no session cookies of its own. Authentication is handled upstream by the Databricks Apps auth proxy, which injects `X-Forwarded-Access-Token` and `X-Forwarded-Email` on every request. Because we use no self-managed cookies and accept no cross-origin requests (see CORS above), the classic CSRF attack surface is effectively nil. If we ever introduce our own session cookies, we must require `SameSite=Strict` + a double-submit CSRF token.

### Input validation

Pydantic schemas apply `Literal` enums on `engagement_type`, `status`, and `fy`; `HttpUrl` validation on URL fields; `max_length` caps on free-text fields; and `str_strip_whitespace`. Invalid payloads return 422.

## Configuration

All settings are managed via environment variables (or `.env` file), loaded by `src/backend/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///strategist_cockpit.db` | SQLite path used when `DATA_BACKEND=sqlite` |
| `DATA_BACKEND` | `sqlite` | `sqlite` (dev / pytest) or `dbsql` (prod, UC + DBSQL via OBO) |
| `DATABRICKS_HOST` | (empty) | Workspace URL — required for `dbsql`, embeds, and KA |
| `DATABRICKS_WAREHOUSE_ID` | `071969b1ec9a91ca` | SQL warehouse for `dbsql` reads/writes |
| `STRATEGO_ENDPOINT_NAME` | (empty) | Serving endpoint for Stratego KA |
| `LAKEVIEW_DASHBOARD_ID` | (empty) | Dashboard ID surfaced at `/impact` (T-201). Empty → page shows fallback card. |
| `GENIE_SPACE_ID` | (empty) | Genie space ID surfaced at `/ask` (T-202). Empty → page shows fallback card. |
| `STRICT_AUTH` | (empty) | Set to `1` in prod so missing `X-Forwarded-Email` / `X-Forwarded-Access-Token` returns 401 instead of dev fallback |
| `ADMIN_EMAILS` | `felix.mutzl@databricks.com,marco.metting@databricks.com` | Comma-separated. Used by `is_admin()` for project-DELETE override. |
| `DEV_USER_EMAIL` | `dev@local` | Local-dev fallback email when `X-Forwarded-Email` is absent. |
| `DATABRICKS_APP_PORT` | `8000` | Port for the FastAPI server |
| `CSP_FRAME_SRC` | (empty) | Space-separated hosts allowed in `frame-src` (dashboard/Genie embeds — set to the workspace host in prod) |
| `CSP_CONNECT_SRC` | (empty) | Space-separated hosts allowed in `connect-src` (KA endpoint, etc.) |

`DATABRICKS_TOKEN` is read automatically by the Databricks SDK when set; the app uses it only as the dev fallback for `current_user_token()` (with a one-shot warning so a misconfigured prod surface is loud).

## Deployment

The app deploys to Databricks Apps via `app.yaml`:

```yaml
command:
  - uvicorn
  - src.backend.main:app
  - --host
  - 0.0.0.0
  - --port
  - "$DATABRICKS_APP_PORT"
```

Production uses `valueFrom` for secrets (`DATABASE_URL`, `STRATEGO_ENDPOINT_NAME`).
