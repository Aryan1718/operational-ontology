"""Health endpoint tests."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health as health_routes
from app.db.session import get_db_session
from app.main import create_application


def test_health_endpoint_returns_expected_response(client: TestClient) -> None:
    """Health endpoint should expose service readiness without secrets."""
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "ontology-api"
    assert payload["database"]["configured"] is True
    assert payload["database"]["database"] == "ontology_dev"
    assert "password" not in str(payload).lower()


def test_database_health_endpoint_returns_ok_when_query_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database health endpoint should report success on a working query."""
    app = create_application()
    app.dependency_overrides[get_db_session] = lambda: iter([SimpleNamespace()])
    monkeypatch.setattr(
        health_routes,
        "check_database_connection",
        lambda session: True,
    )

    with TestClient(app) as client:
        response = client.get("/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_endpoint_hides_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database health endpoint should avoid exposing raw connection errors."""
    app = create_application()
    app.dependency_overrides[get_db_session] = lambda: iter([SimpleNamespace()])

    def raise_error(session: object) -> bool:
        raise RuntimeError("connection refused: postgres://secret")

    monkeypatch.setattr(health_routes, "check_database_connection", raise_error)

    with TestClient(app) as client:
        response = client.get("/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
