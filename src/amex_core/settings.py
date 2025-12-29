from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Root of repo (best-effort). You can override with AMEX_PROJECT_ROOT in env.
    AMEX_PROJECT_ROOT: str = str(Path(__file__).resolve().parents[2])

    # Data directory containing mock JSON
    AMEX_DATA_DIR: str = str(Path(__file__).resolve().parent / "data")

    # API server settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_CORS_ORIGINS: str = "*"  # for demo; tighten in real prod

    # MCP server settings (stdio by default; you can extend later)
    MCP_SERVER_NAME: str = "amex-mock-mcp"


settings = Settings()
