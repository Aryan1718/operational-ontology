"""SQLAlchemy engine and session configuration."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_database_engine() -> Engine:
    """Create the shared SQLAlchemy engine."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine."""
    return create_database_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the shared SQLAlchemy session factory."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_db_session() -> Iterator[Session]:
    """Yield a database session with rollback and close handling."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection(session: Session) -> bool:
    """Return whether the database accepts a basic query."""
    session.execute(text("SELECT 1"))
    return True
