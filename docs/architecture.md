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

### API Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `engagements` | `/api/engagements` | CRUD for engagement records |
| `projects` | `/api/projects` | CRUD for gallery project items |
| `canvas` | `/api/canvas` | Keyword-matched canvas activity summaries |
| `chat` | `/api/chat` | Stratego chatbot (KA proxy or fallback) |

### Database Models

**Engagement**: customer, engagement_title, engagement_type (Focus/One-off/Customer Event), status, fy, quarter, ae, asq_id, asq_url, actionable_outcome, next_steps, related_documents, timeframe

**Project**: name, description, url, thumbnail_url, category, created_at

## Frontend

- **Framework**: React 18 + TypeScript + Vite
- **UI Library**: shadcn/ui (Radix primitives + Tailwind CSS)
- **Routing**: React Router DOM v6
- **Build output**: `static/` directory served by FastAPI

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Home | `/` | Welcome from Stratego + navigation tiles |
| Canvas | `/canvas` | Interactive strategist canvas with popover summaries |
| Engagements | `/engagements` | KPIs, quarter chart, filterable/sortable table with CRUD, view/edit/delete actions |
| Gallery | `/gallery` | Project thumbnail tiles with add/delete |

### Key Components

- `StrategistCanvas` -- Interactive canvas with clickable activity boxes, goal sidebar, and 5 archetype links (Organizer, Builder, Product, Industry, Advisor)
- `StrategoChat` -- Floating chat widget backed by `/api/chat`

## Databricks Integration

### Unity Catalog Assets

| Asset | Type | Description |
|-------|------|-------------|
| `home_felix_mutzl.strategist_canvas.engagement_details` | Delta Table | Strategist engagement data (from CSV) |
| `home_felix_mutzl.strategist_canvas.v_engagements_unified` | View | Joins engagements + ASQ + accounts + revenue |
| `home_felix_mutzl.strategist_canvas.engagements` | View | Pre-existing mapping of strategist to accounts |
| `main.gtm_gold.rpt_c360_overview_unpivoted` | Table | Revenue/consumption metrics by account and period |

### AI/BI Dashboard

The "Strategist Impact Dashboard" visualizes engagement metrics with:
- KPI counters (total engagements, focus accounts, unique customers)
- Engagement timeline by quarter (bar chart)
- Engagement type breakdown (pie chart)
- Filterable detail table

### Genie Space

"Strategist Cockpit Genie" provides natural language queries over the unified engagement view and revenue data.

### Stratego Chat (Knowledge Assistant)

When a serving endpoint is configured via `STRATEGO_ENDPOINT_NAME`, chat queries are proxied to a Databricks Knowledge Assistant. When unavailable, keyword-based fallback responses cover all major topics.

## Configuration

All settings are managed via environment variables (or `.env` file), loaded by `src/backend/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///strategist_cockpit.db` | Database connection string |
| `DATABRICKS_HOST` | (empty) | Workspace URL |
| `DATABRICKS_TOKEN` | (empty) | PAT for API calls |
| `DATABRICKS_WAREHOUSE_ID` | `071969b1ec9a91ca` | SQL warehouse for queries |
| `STRATEGO_ENDPOINT_NAME` | (empty) | Serving endpoint for Stratego KA |
| `DATABRICKS_APP_PORT` | `8000` | Port for the FastAPI server |

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
