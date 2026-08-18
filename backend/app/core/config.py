"""Environment-backed application settings."""

from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import ParseResult, urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    database_scheme: str = Field(default="postgresql+psycopg", alias="DATABASE_SCHEME")
    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="ontology_dev", alias="DATABASE_NAME")
    database_user: str = Field(default="postgres", alias="DATABASE_USER")
    database_password: str = Field(default="change_me", alias="DATABASE_PASSWORD")
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    backend_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="BACKEND_CORS_ORIGINS",
    )
    mcp_remote_enabled: bool = Field(default=False, alias="MCP_REMOTE_ENABLED")
    mcp_server_url: str | None = Field(default=None, alias="MCP_SERVER_URL")
    mcp_token_audience: str | None = Field(default=None, alias="MCP_TOKEN_AUDIENCE")
    mcp_stdio_dev_identity_enabled: bool = Field(
        default=False,
        alias="MCP_STDIO_DEV_IDENTITY_ENABLED",
    )
    mcp_dev_actor_id: str = Field(
        default="ontology-assistant",
        alias="MCP_DEV_ACTOR_ID",
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
    def database_url(self) -> str:
        """Return the complete database URL."""
        if self.database_url_override:
            return self.database_url_override
        return URL.create(
            drivername=self.database_scheme,
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)

    @property
    def parsed_database_url(self) -> ParseResult:
        """Return a parsed database URL without exposing credentials."""
        return urlparse(self.database_url)

    @property
    def database_driver(self) -> str | None:
        """Return the configured database driver scheme."""
        return self.parsed_database_url.scheme or None

    @property
    def database_health_host(self) -> str | None:
        """Return the configured database host for health output."""
        return self.parsed_database_url.hostname or self.database_host

    @property
    def database_health_port(self) -> int | None:
        """Return the configured database port for health output."""
        return self.parsed_database_url.port or self.database_port

    @property
    def database_health_name(self) -> str | None:
        """Return the configured database name for health output."""
        path = self.parsed_database_url.path.lstrip("/")
        return path or self.database_name

    @property
    def is_production(self) -> bool:
        """Return whether the application is running in production mode."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for process-wide reuse."""
    return Settings()
