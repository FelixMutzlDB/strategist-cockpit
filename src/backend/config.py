import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///strategist_cockpit.db"
    use_mock_backend: bool = False
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = "071969b1ec9a91ca"
    stratego_endpoint_name: str = ""
    databricks_app_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
