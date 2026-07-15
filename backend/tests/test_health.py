"""Health endpoint tests."""

from app.core.config import get_settings
from tests.conftest import create_test_client


def test_health_endpoint_returns_expected_response() -> None:
    """Health endpoint should expose service readiness without secrets."""
    client = create_test_client()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    settings = get_settings()
    assert payload["status"] == "ok"
    assert payload["service"] == "ontology-api"
    assert payload["database"]["configured"] is True
    assert payload["database"]["database"] == settings.database_name
    assert "password" not in str(payload).lower()
