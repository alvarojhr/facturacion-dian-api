"""Server-specific runtime settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(".env")


class ServerSettings(BaseSettings):
    """FastAPI runtime settings for the public HTTP server."""

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_allow_origins: str = Field(default="")

    @property
    def allow_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]


server_settings = ServerSettings()
