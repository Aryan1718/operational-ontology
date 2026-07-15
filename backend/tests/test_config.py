"""Settings tests."""

import pytest

from app.core.config import Settings, get_settings


def test_settings_build_database_url_from_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Component variables should build the connection URL."""
    monkeypatch.setenv("DATABASE_SCHEME", "postgresql+psycopg")
    monkeypatch.setenv("DATABASE_HOST", "db.internal")
    monkeypatch.setenv("DATABASE_PORT", "6543")
    monkeypatch.setenv("DATABASE_NAME", "ontology_test")
    monkeypatch.setenv("DATABASE_USER", "ontology")
    monkeypatch.setenv("DATABASE_PASSWORD", "secret")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    settings = Settings()

    assert (
        settings.database_url
        == "postgresql+psycopg://ontology:secret@db.internal:6543/ontology_test"
    )
    assert settings.database_health_host == "db.internal"
    assert settings.database_health_port == 6543
    assert settings.database_health_name == "ontology_test"
    get_settings.cache_clear()


def test_settings_prefer_database_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATABASE_URL should override the assembled component URL."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://override:pass@override-host:5439/override_db",
    )
    get_settings.cache_clear()

    settings = Settings()

    assert (
        settings.database_url
        == "postgresql+psycopg://override:pass@override-host:5439/override_db"
    )
    assert settings.database_driver == "postgresql+psycopg"
    assert settings.database_health_host == "override-host"
    assert settings.database_health_port == 5439
    assert settings.database_health_name == "override_db"
    get_settings.cache_clear()
