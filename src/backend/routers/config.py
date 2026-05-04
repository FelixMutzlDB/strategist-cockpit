"""Public-ish runtime config for the SPA (T-201 / T-202).

The frontend hits /api/config on load to learn:
- The Databricks workspace host (for embed iframe URLs).
- The Lakeview dashboard ID for the /impact page.
- The Genie space ID for the /ask page.

Nothing here is a secret — these are display configuration. We don't gate
this behind ``current_user_email`` because the SPA needs it before it has
the user's session set up, and exposing IDs to anonymous probes is fine
(the embedded surfaces themselves require Databricks auth).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.backend.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigResponse(BaseModel):
    databricks_host: str
    lakeview_dashboard_id: str
    genie_space_id: str
    data_backend: str


@router.get("/", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    return ConfigResponse(
        databricks_host=settings.databricks_host,
        lakeview_dashboard_id=settings.lakeview_dashboard_id,
        genie_space_id=settings.genie_space_id,
        data_backend=settings.data_backend,
    )
