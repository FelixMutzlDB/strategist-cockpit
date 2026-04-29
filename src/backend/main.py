import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.backend.database import init_db
from src.backend.middleware import SecurityHeadersMiddleware
from src.backend.routers import canvas, chat, engagements, projects

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")
    yield


app = FastAPI(title="Strategist Cockpit", version="0.1.0", lifespan=lifespan)

# Same-origin under Databricks Apps in prod, same-origin via the Vite proxy in
# local dev — no CORS needed in either case. Security headers stamped on every
# response (see src/backend/middleware.py).
app.add_middleware(SecurityHeadersMiddleware)

# Include API routers
app.include_router(engagements.router)
app.include_router(projects.router)
app.include_router(canvas.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "strategist-cockpit"}


# Serve the built React SPA. Mounted last so /api/* routes win first.
# StaticFiles handles path canonicalization safely (resolves and verifies the
# resolved path stays inside the directory) — closes F-TM-3 from SDR-4682.
# html=True makes it fall back to index.html for client-routed paths.
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")
