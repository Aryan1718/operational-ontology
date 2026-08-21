"""Shared backend test fixtures."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.authentication import (
    build_bearer_authorization_header,
    create_human_api_token,
)
from app.core.config import get_settings
from app.db.seed import SeedProfile, SeedResult, seed_database
from app.db.session import get_engine, get_session_factory
from app.main import create_application
from app.ontology.actor_context import OntologyRole


def _clear_cached_state() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()



def _configure_test_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_JWT_ISSUER", "ontology-api")
    monkeypatch.setenv("API_JWT_AUDIENCE", "ontology-api-clients")


def build_api_auth_headers(
    *,
    role: OntologyRole = OntologyRole.VIEWER,
    subject: str = "viewer-001",
) -> dict[str, str]:
    settings = get_settings()
    token = create_human_api_token(
        subject=subject,
        roles=(role,),
        settings=settings,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    return {"Authorization": build_bearer_authorization_header(token)}

def _configure_local_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_HOST", "localhost")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_NAME", "ontology_dev")
    monkeypatch.setenv("DATABASE_USER", "postgres")
    monkeypatch.setenv("DATABASE_PASSWORD", "change_me")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _configure_test_auth(monkeypatch)
    _clear_cached_state()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Construct a test client for backend tests."""
    _configure_test_auth(monkeypatch)
    _clear_cached_state()
    app = create_application()
    with TestClient(app) as test_client:
        test_client.headers.update(build_api_auth_headers())
        yield test_client


def create_test_client() -> TestClient:
    """Construct a test client for backend tests."""
    test_client = TestClient(create_application())
    test_client.headers.update(build_api_auth_headers())
    return test_client


@pytest.fixture
def seeded_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[SeedResult, None, None]:
    """Seed the running local PostgreSQL instance with the golden fixture."""
    _configure_local_postgres(monkeypatch)
    result = seed_database(SeedProfile.GOLDEN, reset=True)
    yield result
    _clear_cached_state()


@pytest.fixture
def database_session(
    seeded_database: SeedResult,
) -> Generator[Session, None, None]:
    """Yield a real SQLAlchemy session bound to the seeded PostgreSQL database."""
    del seeded_database
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


@pytest.fixture
def database_client(
    seeded_database: SeedResult,
) -> Generator[TestClient, None, None]:
    """Yield a FastAPI client backed by the seeded PostgreSQL database."""
    del seeded_database
    app = create_application()
    with TestClient(app) as test_client:
        test_client.headers.update(build_api_auth_headers())
        yield test_client
