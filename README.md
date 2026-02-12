# Strategist Cockpit

A Databricks App for data & AI strategists -- combining engagement tracking, the strategist canvas framework, impact dashboards, and a projects gallery in one place.

## Features

- **Home Page**: Welcome from Stratego (AI companion) with navigation to all sections
- **Strategist Canvas**: Interactive framework mapping activities to engagements
- **Impact Dashboard**: Engagement tracking with FY/type/status filters + native AI/BI Dashboard
- **Projects Gallery**: Reusable assets and artefacts with add-new functionality
- **Stratego Chat**: Omnipresent chatbot powered by Databricks Knowledge Assistant
- **Genie Space**: Natural language data exploration over engagement + revenue data

## Tech Stack

- **Frontend**: React + TypeScript + shadcn/ui + Vite
- **Backend**: FastAPI + SQLAlchemy
- **Database**: SQLite (dev) / PostgreSQL (Lakebase prod)
- **Data**: Databricks Delta tables, Unity Catalog
- **AI**: Knowledge Assistant, Genie Space, AI/BI Dashboards

## Local Development

```bash
# Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Seed the database
python -m data.seed_database

# Start the backend
uvicorn src.backend.main:app --reload --port 8000

# In another terminal, start the frontend dev server
cd src/ui
npm install
npm run dev
```

## Build for Deployment

```bash
cd src/ui && npm run build
# This outputs to /static which is served by FastAPI
```

## Databricks Assets

| Asset | Description |
|-------|-------------|
| `home_felix_mutzl.strategist_canvas.engagement_details` | Delta table with strategist engagement data |
| `home_felix_mutzl.strategist_canvas.v_engagements_unified` | Unified view joining engagements + ASQ + accounts + revenue |
| `home_felix_mutzl.strategist_canvas.engagements` | Existing view mapping strategist to accounts |
| Strategist Impact Dashboard | AI/BI Dashboard with engagement metrics |
| Strategist Cockpit Genie | Genie Space for natural language data exploration |

## Project Structure

```
strategist-cockpit/
├── app.yaml                # Databricks Apps config
├── docker-compose.yml      # Local PostgreSQL (optional)
├── requirements.txt        # Python dependencies
├── data/                   # CSV data and seeding scripts
├── src/
│   ├── backend/            # FastAPI backend
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── routers/
│   └── ui/                 # React frontend
│       └── src/
│           ├── pages/
│           └── components/
├── static/                 # Built frontend (generated)
└── databricks/             # Databricks setup scripts
```
