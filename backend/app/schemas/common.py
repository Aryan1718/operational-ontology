"""Shared API schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


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


class ApiBaseModel(BaseModel):
    """Shared API model configuration."""

    model_config = ConfigDict(populate_by_name=True)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class ResponseMeta(ApiBaseModel):
    """Shared metadata returned with API success and error envelopes."""

    request_id: str = Field(alias="requestId")
    timestamp: datetime = Field(default_factory=utc_now)


class ApiErrorDetail(ApiBaseModel):
    """Structured API error payload."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(ApiBaseModel):
    """Structured API error response."""

    error: ApiErrorDetail
    meta: ResponseMeta


ResponseDataT = TypeVar("ResponseDataT")


class SuccessResponse(ApiBaseModel, Generic[ResponseDataT]):
    """Structured API success response."""

    data: ResponseDataT
    meta: ResponseMeta
