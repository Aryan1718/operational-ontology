"""Shared FastAPI dependencies."""

from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Provide cached application settings to route handlers."""
    return get_settings()
