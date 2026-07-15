"""Health-check routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.db.session import check_database_connection, get_db_session
from app.schemas.common import (
    DatabaseConnectionHealthResponse,
    DatabaseHealth,
    HealthResponse,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def read_health(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    """Return a simple process health response."""
    return HealthResponse(
        status="ok",
        service="ontology-api",
        database=DatabaseHealth(
            configured=bool(settings.database_url),
            driver=settings.database_driver,
            host=settings.database_health_host,
            port=settings.database_health_port,
            database=settings.database_health_name,
        ),
    )


@router.get(
    "/health/database",
    response_model=DatabaseConnectionHealthResponse,
    tags=["health"],
)
def read_database_health(
    session: Annotated[Session, Depends(get_db_session)],
) -> DatabaseConnectionHealthResponse:
    """Return database connectivity without exposing internal errors."""
    try:
        check_database_connection(session)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc

    return DatabaseConnectionHealthResponse(status="ok")
