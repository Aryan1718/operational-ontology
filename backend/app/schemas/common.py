"""Shared API schemas."""

from typing import Any

from pydantic import BaseModel, Field


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


class DatabaseConnectionHealthResponse(BaseModel):
    """Database connectivity health response."""

    status: str


class ApiErrorDetail(BaseModel):
    """Structured API error payload."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Structured API error response."""

    error: ApiErrorDetail
