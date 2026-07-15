"""Logging configuration helpers."""

import logging

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure a minimal process-wide logging setup."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
