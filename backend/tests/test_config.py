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


def test_settings_include_mcp_foundation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP settings should load through the shared configuration system."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MCP_REMOTE_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_URL", "https://example.test/mcp")
    monkeypatch.setenv("MCP_TOKEN_AUDIENCE", "ontology-mcp")
    monkeypatch.setenv("MCP_STDIO_DEV_IDENTITY_ENABLED", "false")
    get_settings.cache_clear()

    settings = Settings()

    assert settings.is_production is True
    assert settings.mcp_remote_enabled is True
    assert settings.mcp_server_url == "https://example.test/mcp"
    assert settings.mcp_token_audience == "ontology-mcp"
    assert settings.mcp_stdio_dev_identity_enabled is False
    assert settings.mcp_dev_actor_id == "ontology-assistant"
    get_settings.cache_clear()
