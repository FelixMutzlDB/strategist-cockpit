from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///strategist_cockpit.db"
    use_mock_backend: bool = False
    databricks_host: str = ""
    databricks_warehouse_id: str = "071969b1ec9a91ca"
    stratego_endpoint_name: str = ""
    databricks_app_port: int = 8000

    # T-206: which data layer to use.
    # - "sqlite": SQLAlchemy + SQLite (dev / pytest default).
    # - "dbsql":  Databricks SQL warehouse over OBO (logfood + prod).
    data_backend: Literal["sqlite", "dbsql"] = "sqlite"

    # T-206: UC catalog/schema for app-managed write targets and read views.
    # Centralised so test fixtures and ops scripts can override without code edits.
    uc_catalog: str = "main"
    uc_schema: str = "field_strategist_cockpit"

    # T-201 / T-202: dashboard + Genie embed surfaces. Empty values disable
    # the corresponding embed and the UI shows a "View in Databricks" fallback.
    lakeview_dashboard_id: str = ""
    genie_space_id: str = ""


settings = Settings()
