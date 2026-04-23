# Development Guide

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Git

## Quick Start

```bash
# Clone the repository
git clone https://github.com/FelixMutzlDB/strategist-cockpit.git
cd strategist-cockpit

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Seed the SQLite database from CSV
python -m data.seed_database

# Start the backend (port 8000)
uvicorn src.backend.main:app --reload --port 8000

# In a second terminal, start the frontend dev server (port 5173)
cd src/ui
npm install
npm run dev
```

The frontend dev server proxies `/api` requests to the backend at `localhost:8000` (configured in `vite.config.ts`).

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
DATABASE_URL=sqlite:///strategist_cockpit.db
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE_ID=071969b1ec9a91ca
STRATEGO_ENDPOINT_NAME=         # leave empty for fallback chat
```

## Database

### Local Development (SQLite)

The default `DATABASE_URL` uses SQLite. The database file `strategist_cockpit.db` is created automatically on first run and excluded via `.gitignore`.

### Seeding Data

```bash
python -m data.seed_database
```

This reads `data/engagements.csv` and inserts records into the `engagements` table, plus creates default projects (Systems of Intelligence, Innovation Factory).

### Production (Lakebase PostgreSQL)

Set `DATABASE_URL` to the Lakebase connection string:
```
postgresql://user:token@host:port/databricks_postgres?sslmode=require
```

## Frontend Development

```bash
cd src/ui
npm install
npm run dev        # Dev server with HMR at http://localhost:5173
npm run build      # Production build to ../../static/
npm run preview    # Preview production build locally
```

### shadcn/ui Components

UI components live in `src/ui/src/components/ui/`. To add new shadcn components:

```bash
cd src/ui
npx shadcn@latest add button   # example
```

## Building for Deployment

```bash
# Build the frontend
cd src/ui && npm run build && cd ../..

# The static/ directory is now ready to be served by FastAPI
```

## Running Tests

```bash
# From project root with venv activated
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Databricks Apps Deployment

```bash
# Install Databricks CLI if not present
# https://docs.databricks.com/dev-tools/cli/install.html

# Build the frontend first
cd src/ui && npm run build && cd ../..

# Deploy using the Databricks CLI
databricks apps deploy strategist-cockpit --source-code-path .
```

The `app.yaml` configuration controls the runtime command and environment variables. Secrets are injected via `valueFrom` references.

## Project Structure

```
strategist-cockpit/
├── app.yaml                    # Databricks Apps configuration
├── pyproject.toml              # Python project metadata
├── requirements.txt            # Python dependencies
├── data/
│   ├── engagements.csv         # Source engagement data
│   ├── seed_database.py        # Database seeder script
│   └── stratego_context.md     # KA context document
├── docs/                       # Project documentation
├── src/
│   ├── backend/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Settings (env vars)
│   │   ├── database.py         # SQLAlchemy engine/session
│   │   ├── models.py           # ORM models
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── routers/
│   │       ├── engagements.py  # CRUD endpoints
│   │       ├── projects.py     # Gallery endpoints
│   │       ├── canvas.py       # Canvas summaries
│   │       └── chat.py         # Stratego chatbot
│   └── ui/
│       ├── index.html          # HTML entry point
│       ├── package.json        # Frontend dependencies
│       ├── vite.config.ts      # Vite build config
│       ├── public/
│       │   └── compass.svg     # Favicon
│       └── src/
│           ├── App.tsx          # Root component + routing
│           ├── lib/
│           │   ├── api.ts       # API client functions
│           │   └── utils.ts     # Tailwind utilities
│           ├── pages/
│           │   ├── Home.tsx
│           │   ├── Canvas.tsx
│           │   ├── Engagements.tsx
│           │   └── Gallery.tsx
│           └── components/
│               ├── StrategistCanvas.tsx
│               ├── StrategoChat.tsx
│               └── ui/          # shadcn/ui primitives
├── static/                      # Built frontend (generated)
└── tests/                       # Test suite
```
