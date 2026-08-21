from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.authentication import (
    authenticate_human_api_request,
    build_bearer_authorization_header,
    create_human_api_token,
)
from app.api.dependencies import get_function_engine
from app.core.config import Settings, get_settings
from app.main import create_application
from app.mcp.auth import HttpMcpIdentityResolver
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)
from app.runtime.function_engine import ExecutedFunction
from app.schemas.functions import FunctionExecutionResponse


class _StubFunctionEngine:
    def execute(self, **_: object) -> ExecutedFunction:
        return ExecutedFunction(
            payload=FunctionExecutionResponse(
                functionName="getInventoryAvailability",
                result={"partId": "PART-B"},
                warnings=[],
            )
        )


class _FakeRemoteVerifier:
    async def verify_bearer_token(self, bearer_token: str) -> ActorContext:
        del bearer_token
        return ActorContext(
            actor_id="remote-subject",
            actor_type=ActorType.HUMAN,
            roles=(OntologyRole.ADMIN, OntologyRole.OPERATIONS_MANAGER),
            invocation_source=InvocationSource.WEB_APP,
        )


def _configure_auth_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_JWT_ISSUER", "ontology-api")
    monkeypatch.setenv("API_JWT_AUDIENCE", "ontology-api-clients")
    get_settings.cache_clear()
    return get_settings()


def _build_token(
    *,
    settings: Settings,
    subject: str,
    roles: tuple[OntologyRole, ...],
    extra_claims: dict[str, object] | None = None,
    expires_at: datetime | None = None,
) -> str:
    return create_human_api_token(
        subject=subject,
        roles=roles,
        settings=settings,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=1)),
        extra_claims=extra_claims,
    )


def _protected_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _configure_auth_settings(monkeypatch)
    app = create_application()
    app.dependency_overrides[get_function_engine] = lambda: _StubFunctionEngine()
    return TestClient(app)


def test_missing_credentials_return_401(monkeypatch: pytest.MonkeyPatch) -> None:
    with _protected_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/functions/getInventoryAvailability/execute",
            json={"parameters": {"partId": "PART-B"}},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_malformed_bearer_credentials_return_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _protected_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/functions/getInventoryAvailability/execute",
            headers={"Authorization": "Token not-a-bearer"},
            json={"parameters": {"partId": "PART-B"}},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_invalid_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_auth_settings(monkeypatch)
    token = _build_token(
        settings=settings,
        subject="viewer-001",
        roles=(OntologyRole.VIEWER,),
    )
    corrupted = token[:-1] + ("a" if token[-1] != "a" else "b")

    with _protected_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/functions/getInventoryAvailability/execute",
            headers={"Authorization": build_bearer_authorization_header(corrupted)},
            json={"parameters": {"partId": "PART-B"}},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_expired_token_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_auth_settings(monkeypatch)
    token = _build_token(
        settings=settings,
        subject="viewer-001",
        roles=(OntologyRole.VIEWER,),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    with _protected_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/functions/getInventoryAvailability/execute",
            headers={"Authorization": build_bearer_authorization_header(token)},
            json={"parameters": {"partId": "PART-B"}},
        )

    assert response.status_code == 401


def test_valid_viewer_token_creates_human_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configure_auth_settings(monkeypatch)
    actor = authenticate_human_api_request(
        authorization_header=build_bearer_authorization_header(
            _build_token(
                settings=settings,
                subject="viewer-001",
                roles=(OntologyRole.VIEWER,),
            )
        ),
        settings=settings,
    )

    assert actor.actor_id == "viewer-001"
    assert actor.actor_type is ActorType.HUMAN
    assert actor.roles == (OntologyRole.VIEWER,)
    assert actor.invocation_source is InvocationSource.API


def test_valid_planner_token_creates_human_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configure_auth_settings(monkeypatch)
    actor = authenticate_human_api_request(
        authorization_header=build_bearer_authorization_header(
            _build_token(
                settings=settings,
                subject="planner-001",
                roles=(OntologyRole.PLANNER,),
            )
        ),
        settings=settings,
    )

    assert actor.actor_id == "planner-001"
    assert actor.actor_type is ActorType.HUMAN
    assert actor.roles == (OntologyRole.PLANNER,)
    assert actor.invocation_source is InvocationSource.API


def test_actor_id_comes_from_validated_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configure_auth_settings(monkeypatch)
    actor = authenticate_human_api_request(
        authorization_header=build_bearer_authorization_header(
            _build_token(
                settings=settings,
                subject="planner-002",
                roles=(OntologyRole.PLANNER,),
            )
        ),
        settings=settings,
    )

    assert actor.actor_id == "planner-002"


def test_human_token_ignores_ai_like_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_auth_settings(monkeypatch)
    actor = authenticate_human_api_request(
        authorization_header=build_bearer_authorization_header(
            _build_token(
                settings=settings,
                subject="planner-001",
                roles=(OntologyRole.PLANNER,),
                extra_claims={
                    "actorType": "ai_agent",
                    "invocationSource": "mcp",
                    "trustedExecutionContext": True,
                },
            )
        ),
        settings=settings,
    )

    assert actor.actor_type is ActorType.HUMAN
    assert actor.roles == (OntologyRole.PLANNER,)
    assert actor.invocation_source is InvocationSource.API


def test_human_token_cannot_authenticate_as_ai_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configure_auth_settings(monkeypatch)
    token = _build_token(
        settings=settings,
        subject="fake-ai",
        roles=(OntologyRole.AI_AGENT,),
    )

    with pytest.raises(Exception):
        authenticate_human_api_request(
            authorization_header=build_bearer_authorization_header(token),
            settings=settings,
        )


def test_authenticated_but_unauthorized_operation_returns_403(
    database_client: TestClient,
) -> None:
    settings = get_settings()
    viewer_token = _build_token(
        settings=settings,
        subject="viewer-001",
        roles=(OntologyRole.VIEWER,),
    )

    response = database_client.post(
        "/api/v1/actions/generateMitigationPlan",
        headers={
            "Authorization": build_bearer_authorization_header(viewer_token),
            "X-Actor-Role": "Admin",
        },
        json={"parameters": {"riskEventId": "RISK-102", "roles": ["Planner"]}},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "OPERATION_NOT_PERMITTED"


def test_authorized_operation_continues_to_work(database_client: TestClient) -> None:
    settings = get_settings()
    planner_token = _build_token(
        settings=settings,
        subject="planner-001",
        roles=(OntologyRole.PLANNER,),
    )

    response = database_client.post(
        "/api/v1/actions/generateMitigationPlan",
        headers={"Authorization": build_bearer_authorization_header(planner_token)},
        json={"parameters": {"riskEventId": "RISK-102"}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["result"]["status"] == "draft"


def test_public_health_route_remains_accessible_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_auth_settings(monkeypatch)

    with TestClient(create_application()) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_mcp_ai_normalization_remains_unchanged() -> None:
    resolver = HttpMcpIdentityResolver(_FakeRemoteVerifier())

    actor = pytest.importorskip("asyncio").run(
        resolver.resolve_actor("Bearer trusted-token")
    )

    assert actor.actor_type is ActorType.AI_AGENT
    assert actor.roles == (OntologyRole.AI_AGENT,)
    assert actor.invocation_source is InvocationSource.MCP
