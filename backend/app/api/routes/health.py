"""Health-check route."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.schemas.common import DatabaseHealth, HealthResponse

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
            host=settings.database_host,
            port=settings.database_port,
            database=settings.database_name,
        ),
    )
