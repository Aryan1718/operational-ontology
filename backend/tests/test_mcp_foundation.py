"""Phase 1 MCP foundation tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app.core.config import Settings, get_settings
from app.main import create_application
from app.mcp.auth import (
    HttpMcpIdentityResolver,
    McpAuthenticationError,
    UnconfiguredRemoteMcpTokenVerifier,
    build_stdio_development_identity_resolver,
)
from app.mcp.server import create_mcp_server, get_mcp_server_definition
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole


class _FakeRemoteVerifier:
    async def verify_bearer_token(self, bearer_token: str) -> ActorContext:
        del bearer_token
        return ActorContext(
            actor_id="remote-subject",
            actor_type=ActorType.HUMAN,
            roles=(OntologyRole.ADMIN, OntologyRole.OPERATIONS_MANAGER),
            invocation_source=InvocationSource.WEB_APP,
        )


def _build_settings(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
) -> Settings:
    monkeypatch.setenv("APP_ENV", overrides.pop("APP_ENV", "development"))
    monkeypatch.setenv(
        "MCP_REMOTE_ENABLED",
        overrides.pop("MCP_REMOTE_ENABLED", "false"),
    )
    monkeypatch.setenv(
        "MCP_STDIO_DEV_IDENTITY_ENABLED",
        overrides.pop("MCP_STDIO_DEV_IDENTITY_ENABLED", "false"),
    )
    monkeypatch.setenv(
        "MCP_TOKEN_AUDIENCE",
        overrides.pop("MCP_TOKEN_AUDIENCE", "ontology-mcp"),
    )
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return get_settings()


def test_application_initializes_with_mcp_support_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_settings(monkeypatch, MCP_REMOTE_ENABLED="true")

    app = create_application()

    assert app.state.mcp_server is not None
    mount_paths = [route.path for route in app.router.routes if isinstance(route, Mount)]
    assert "/mcp" in mount_paths


def test_existing_fastapi_routes_still_initialize_when_mcp_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_settings(monkeypatch, MCP_REMOTE_ENABLED="true")
    app = create_application()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "ontology-api"


def test_mcp_route_returns_auth_failure_when_remote_mode_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_settings(monkeypatch, MCP_REMOTE_ENABLED="true")
    app = create_application()

    with TestClient(app) as client:
        response = client.get("/mcp")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "MCP_AUTHENTICATION_FAILED",
            "message": "Bearer authentication is required.",
        }
    }


def test_mcp_route_is_not_mounted_when_remote_mode_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_settings(monkeypatch, MCP_REMOTE_ENABLED="false")
    app = create_application()

    with TestClient(app) as client:
        response = client.get("/mcp")

    assert response.status_code == 404


def test_stdio_and_http_modes_use_the_same_server_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings(monkeypatch)

    definition = get_mcp_server_definition()
    server = create_mcp_server(settings)

    assert server.name == definition.name
    assert server.instructions == definition.instructions
    assert server.settings.streamable_http_path == "/"
    assert server.settings.stateless_http is True
    assert server.settings.json_response is True


def test_stdio_development_identity_requires_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings(monkeypatch, MCP_STDIO_DEV_IDENTITY_ENABLED="false")

    resolver = build_stdio_development_identity_resolver(settings)

    with pytest.raises(McpAuthenticationError, match="disabled"):
        resolver.resolve_actor()


def test_stdio_development_identity_returns_trusted_ai_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings(monkeypatch, MCP_STDIO_DEV_IDENTITY_ENABLED="true")

    actor = build_stdio_development_identity_resolver(settings).resolve_actor()

    assert actor.actor_id == "ontology-assistant"
    assert actor.actor_type is ActorType.AI_AGENT
    assert actor.roles == (OntologyRole.AI_AGENT,)
    assert actor.invocation_source is InvocationSource.MCP


def test_stdio_development_identity_is_blocked_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings(
        monkeypatch,
        APP_ENV="production",
        MCP_STDIO_DEV_IDENTITY_ENABLED="true",
    )

    resolver = build_stdio_development_identity_resolver(settings)

    with pytest.raises(McpAuthenticationError, match="production"):
        resolver.resolve_actor()


def test_remote_identity_cannot_escalate_roles_from_verifier_output() -> None:
    resolver = HttpMcpIdentityResolver(_FakeRemoteVerifier())

    actor = asyncio.run(resolver.resolve_actor("Bearer trusted-token"))

    assert actor.actor_id == "remote-subject"
    assert actor.actor_type is ActorType.AI_AGENT
    assert actor.roles == (OntologyRole.AI_AGENT,)
    assert actor.invocation_source is InvocationSource.MCP


def test_remote_authentication_fails_closed_when_identity_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings(monkeypatch, MCP_REMOTE_ENABLED="true")
    resolver = HttpMcpIdentityResolver(UnconfiguredRemoteMcpTokenVerifier(settings))

    with pytest.raises(McpAuthenticationError, match="not configured"):
        asyncio.run(resolver.resolve_actor("Bearer trusted-token"))


def test_application_lifespan_with_mcp_enabled_starts_and_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_settings(monkeypatch, MCP_REMOTE_ENABLED="true")
    app = create_application()

    with TestClient(app) as client:
        health_response = client.get("/health")
        mcp_response = client.get("/mcp")

    assert health_response.status_code == 200
    assert mcp_response.status_code == 401
    assert app.state.mcp_server is not None
