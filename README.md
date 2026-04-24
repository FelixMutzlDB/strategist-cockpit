# Strategist Cockpit

A Databricks App for a Data & AI Strategist to track engagements, navigate the Strategist Canvas framework, surface impact metrics, and curate a gallery of reusable assets. Ships with a floating "Stratego" chatbot wired to a Databricks Knowledge Assistant.

> New here? Read [`CLAUDE.md`](./CLAUDE.md) first — it's the fastest way to get the lay of the land. Open backlog lives in [`docs/tasks/todo.md`](./docs/tasks/todo.md).

## Features

- **Home** – Welcome from Stratego + navigation tiles
- **Strategist Canvas** – Interactive framework with 5 archetype links (Organizer, Builder, Product, Industry, Advisor); click any box for engagement summaries
- **Engagements** – KPIs, quarter chart, filterable + sortable table, full CRUD with view/edit/delete actions (absorbed the former `/impact` and `/data-entry` pages)
- **Projects Gallery** – Thumbnail tiles for reusable assets with "Add New"
- **Stratego Chat** – Floating widget proxying a Databricks Knowledge Assistant endpoint (with a minimal fallback when offline)

## Tech stack

- **Frontend** – React 18 + TypeScript + Vite + shadcn/ui (Tailwind + Radix)
- **Backend** – FastAPI + SQLAlchemy 2 + Pydantic v2
- **Database** – SQLite (local dev), Lakebase PostgreSQL (planned for production)
- **Databricks** – Unity Catalog tables/views, AI/BI Dashboard, Genie Space, Model Serving (KA)

## Prerequisites

- Python 3.10+
- Node 18+ and npm
- Databricks CLI (for deploy) and a PAT for the target workspace

## Quick start

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m data.seed_database
uvicorn src.backend.main:app --reload --port 8000

# Frontend (second terminal) — dev server at :5173, proxies /api to :8000
cd src/ui && npm install && npm run dev
```

Copy `.env.example` to `.env` and fill in `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `STRATEGO_ENDPOINT_NAME` as needed. Without a KA endpoint the chat falls back to a minimal offline response.

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v                 # unit tests
python -m pytest tests/ -m integration -v  # Databricks integration tests (needs creds)
```

## Build & deploy

```bash
# Build the SPA into ../../static
cd src/ui && npm run build && cd ../..

# Deploy to Databricks Apps
databricks apps deploy strategist-cockpit --source-code-path .
```

The app is served by FastAPI: `/api/*` hits the backend, everything else falls through to the built SPA in `static/`. Configuration lives in `app.yaml`; secrets are injected via `valueFrom`.

## Documentation

- [`CLAUDE.md`](./CLAUDE.md) – project context, conventions, known rough edges, working mode
- [`docs/architecture.md`](./docs/architecture.md) – system design, integration points, configuration
- [`docs/api-reference.md`](./docs/api-reference.md) – REST endpoints with examples
- [`docs/development.md`](./docs/development.md) – setup, tooling, project structure
- [`docs/tasks/todo.md`](./docs/tasks/todo.md) – prioritized backlog with test criteria
- [`docs/deployment.md`](./docs/deployment.md) – links to the SDR questionnaire and design doc for logfood deployment

## Databricks assets

| Asset | Type | Description |
|-------|------|-------------|
| `home_felix_mutzl.strategist_canvas.engagement_details` | Delta table | Strategist engagement data (from CSV) |
| `home_felix_mutzl.strategist_canvas.v_engagements_unified` | View | Engagements joined with ASQ + accounts + revenue |
| `home_felix_mutzl.strategist_canvas.engagements` | View | Pre-existing strategist-to-account mapping |
| `main.gtm_gold.rpt_c360_overview_unpivoted` | Table | Account revenue/consumption per period |
| Strategist Impact Dashboard (Felix) | Lakeview | Built via `scripts/build_dashboard.py` — not yet embedded in the app (see backlog T-201) |
| Strategist Cockpit Genie | Genie Space | Not yet embedded in the app |
| Stratego Knowledge Assistant | Serving endpoint | Configured via `STRATEGO_ENDPOINT_NAME` |

## Project origins

Originally scaffolded with Cursor; ongoing development happens in Claude Code. See [`CLAUDE.md`](./CLAUDE.md) for the working mode we apply to every change.
