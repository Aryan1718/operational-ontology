"""Environment-backed application settings."""

from functools import lru_cache
from typing import Any
from urllib.parse import ParseResult, urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/ontology_dev",
        alias="DATABASE_URL",
    )
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, value: Any) -> list[str]:
        """Accept comma-delimited or list-style origin settings."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        raise TypeError(
            "BACKEND_CORS_ORIGINS must be a list or comma-separated string."
        )

    @property
    def parsed_database_url(self) -> ParseResult:
        """Return a parsed database URL without exposing credentials."""
        return urlparse(self.database_url)

    @property
    def database_driver(self) -> str | None:
        """Return the configured database driver scheme."""
        return self.parsed_database_url.scheme or None

    @property
    def database_host(self) -> str | None:
        """Return the configured database host."""
        return self.parsed_database_url.hostname

    @property
    def database_port(self) -> int | None:
        """Return the configured database port."""
        return self.parsed_database_url.port

    @property
    def database_name(self) -> str | None:
        """Return the configured database name."""
        path = self.parsed_database_url.path.lstrip("/")
        return path or None


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for process-wide reuse."""
    return Settings()
