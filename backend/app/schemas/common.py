"""Shared API schemas."""

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    """Database configuration status without secret values."""

    configured: bool
    driver: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str
    service: str
    database: DatabaseHealth
