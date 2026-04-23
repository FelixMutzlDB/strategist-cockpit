import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from src.backend.database import init_db
from src.backend.routers import engagements, projects, canvas, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")
    yield


app = FastAPI(title="Strategist Cockpit", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(engagements.router)
app.include_router(projects.router)
app.include_router(canvas.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "strategist-cockpit"}


# Serve React static files (built frontend)
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(static_dir / "index.html"))
