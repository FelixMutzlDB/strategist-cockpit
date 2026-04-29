# Architecture

## Overview

Strategist Cockpit is a full-stack Databricks App with a FastAPI backend and React frontend. It integrates with Databricks Unity Catalog, AI/BI Dashboards, Genie Spaces, and Model Serving endpoints.

```
┌─────────────────────────────────────────────────────┐
│                   Browser (React)                    │
│  Home  │  Canvas  │  Engagements  │  Gallery          │
│                  + Stratego Chat                     │
└────────────────────┬────────────────────────────────┘
                     │ /api/*
┌────────────────────▼────────────────────────────────┐
│              FastAPI Backend (uvicorn)                │
│  routers: engagements, projects, canvas, chat        │
│  SQLAlchemy ORM  │  Pydantic schemas                 │
│  SecurityHeadersMiddleware (CSP, X-Frame-Options …)  │
└───────┬──────────┬──────────────────┬───────────────┘
        │          │                  │
   ┌────▼───┐  ┌──▼──────────┐  ┌───▼──────────────┐
   │SQLite/ │  │ Databricks  │  │ Databricks Model │
   │Lakebase│  │ Unity Cat.  │  │ Serving (Stratego│
   │  (DB)  │  │ Delta Tables│  │ KA endpoint)     │
   └────────┘  └──────┬──────┘  └──────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   engagement    v_engagements   rpt_c360_
   _details      _unified        overview_
                                 unpivoted
```

## Backend

- **Framework**: FastAPI 0.115+
- **ORM**: SQLAlchemy 2.0+ with declarative models
- **Validation**: Pydantic 2.10+ / pydantic-settings
- **Database**: SQLite (local dev), Lakebase PostgreSQL (production)
- **Entry point**: `src/backend/main.py`
- **Security middleware**: `src/backend/middleware.py` stamps CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy on every response.

### API Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `engagements` | `/api/engagements` | CRUD with query filtering (fy, engagement_type, status, customer) |
| `projects` | `/api/projects` | CRUD for gallery project items |
| `canvas` | `/api/canvas` | Keyword-matched canvas activity summaries |
| `chat` | `/api/chat` | Stratego chatbot (KA proxy with offline fallback) |

### Database Models

**Engagement**: customer, engagement_title, engagement_type (Focus/One-off/Customer Event/Tbc), status, fy, quarter, ae, asq_id, asq_url, uco_ids, actionable_outcome, next_steps, related_documents, timeframe.

**Project**: name, description, url, thumbnail_url, category, created_at.

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
| Engagements | `/engagements` | KPIs, quarter chart, filter bar (global search + FY + type + status dropdowns), sortable table with per-column filters, CRUD with view/edit/delete actions. Absorbs what used to live under `/impact` and `/data-entry`. |
| Gallery | `/gallery` | Project thumbnail tiles with add/delete |

### Key Components

- `StrategistCanvas` — Interactive canvas with clickable activity boxes, goal sidebar, and 5 archetype links (Organizer, Builder, Product, Industry, Advisor). Each clickable box has a unique activity slug even when the same label appears in multiple positions.
- `StrategoChat` — Floating chat widget backed by `/api/chat`.

## Databricks Integration

### Unity Catalog Assets

| Asset | Type | Description |
|-------|------|-------------|
| `main.field_strategist_cockpit.engagement_details` | Delta Table | Canonical engagement records |
| `main.field_strategist_cockpit.v_engagements_unified` | View | Joins engagements + ASQ + accounts + revenue |
| `main.field_strategist_cockpit.engagements` | View | Strategist → account mapping |
| `main.gtm_gold.rpt_c360_overview_unpivoted` | Table | Revenue/consumption metrics by account and period |

> Historical note: these assets previously lived under `home_felix_mutzl.strategist_canvas.*`. The migration to `main.field_strategist_cockpit.*` is tracked as backlog item T-206.

**Sync direction (policy).** Lakebase is the canonical store for app-managed state (`engagement`, `project` rows produced by the FastAPI routers). The UC tables in `main.field_strategist_cockpit.*` are an analytic projection built **from** Lakebase by a scheduled DLT pipeline. The reverse direction — UC → Lakebase — is **not used and not permitted**: per Databricks platform policy, syncing customer-influenced UC data back into Lakebase isn't allowed.

### AI/BI Dashboard

The "Strategist Impact Dashboard" is defined in `scripts/build_dashboard.py` (Lakeview REST). Five pages: Executive Summary, Focus Engagements, One-off Engagements, Impact Analysis, Global Filters. The in-app `/impact` embed is tracked as T-201.

### Genie Space

"Strategist Cockpit Genie" provides natural language queries over the unified engagement view and revenue data. In-app embed is tracked as T-202.

### Stratego Chat (Knowledge Assistant)

When `STRATEGO_ENDPOINT_NAME` is configured, `/api/chat` proxies messages to a Databricks Knowledge Assistant via `databricks-sdk`. When the endpoint is not configured (local dev without creds), the router returns a single short offline message — no keyword ladder.

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
| `DATABASE_URL` | `sqlite:///strategist_cockpit.db` | Database connection string |
| `DATABRICKS_HOST` | (empty) | Workspace URL |
| `DATABRICKS_WAREHOUSE_ID` | `071969b1ec9a91ca` | SQL warehouse for queries |
| `STRATEGO_ENDPOINT_NAME` | (empty) | Serving endpoint for Stratego KA |
| `DATABRICKS_APP_PORT` | `8000` | Port for the FastAPI server |
| `CSP_FRAME_SRC` | (empty) | Space-separated hosts allowed in `frame-src` (dashboard/Genie embeds) |
| `CSP_CONNECT_SRC` | (empty) | Space-separated hosts allowed in `connect-src` (KA endpoint, etc.) |

`DATABRICKS_TOKEN` is read automatically by the Databricks SDK when set; the app does not surface it as a Pydantic setting.

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
