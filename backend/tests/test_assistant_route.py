from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.api.dependencies import get_assistant_service
from app.assistant.events import AssistantEvent
from app.assistant.runner import AssistantRunner
from app.assistant.schemas import AssistantChatRequest
from app.assistant.service import AssistantService
from app.core.config import get_settings
from app.main import create_application
from app.mcp.server import create_mcp_server
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole
from tests.conftest import build_api_auth_headers


class _RouteRunner(AssistantRunner):
    async def run_stream(self, **_: object):
        yield AssistantEvent(event="message.delta", data={"delta": "Supplier S-102 impacts ORD-881."})
        yield AssistantEvent(
            event="tool.started",
            data={"toolName": "findImpactedOrders", "toolCallId": "tool-1"},
        )
        yield AssistantEvent(
            event="evidence.added",
            data={
                "evidence": {
                    "objectType": "CustomerOrder",
                    "objectId": "ORD-881",
                    "title": "Customer Order ORD-881",
                    "href": "/objects/CustomerOrder/ORD-881",
                }
            },
        )
        yield AssistantEvent(
            event="tool.completed",
            data={
                "toolName": "generateMitigationPlan",
                "toolCallId": "tool-2",
                "createdObject": {
                    "objectType": "MitigationPlan",
                    "objectId": "PLAN-123",
                    "href": "/objects/MitigationPlan/PLAN-123",
                },
            },
        )


def _build_service() -> AssistantService:
    settings = get_settings()
    return AssistantService(
        settings=settings,
        mcp_server=create_mcp_server(settings),
        runner=_RouteRunner(),
    )


def test_assistant_route_requires_authentication(monkeypatch) -> None:
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_JWT_ISSUER", "ontology-api")
    monkeypatch.setenv("API_JWT_AUDIENCE", "ontology-api-clients")
    get_settings.cache_clear()

    with TestClient(create_application()) as client:
        response = client.post("/api/v1/assistant/chat", json={"message": "hello"})

    assert response.status_code == 401


def test_assistant_route_streams_normalized_sse(monkeypatch) -> None:
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_JWT_ISSUER", "ontology-api")
    monkeypatch.setenv("API_JWT_AUDIENCE", "ontology-api-clients")
    get_settings.cache_clear()

    app = create_application()
    app.dependency_overrides[get_assistant_service] = _build_service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=build_api_auth_headers(role=OntologyRole.PLANNER, subject="planner-001"),
            json={"message": "Create the draft mitigation plan for RISK-102."},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run.started" in response.text
    assert "event: message.delta" in response.text
    assert "event: tool.started" in response.text
    assert "event: evidence.added" in response.text
    assert "event: tool.completed" in response.text
    assert "event: run.completed" in response.text


def test_assistant_route_rejects_blank_message(monkeypatch) -> None:
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_JWT_ISSUER", "ontology-api")
    monkeypatch.setenv("API_JWT_AUDIENCE", "ontology-api-clients")
    get_settings.cache_clear()

    with TestClient(create_application()) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=build_api_auth_headers(role=OntologyRole.PLANNER, subject="planner-001"),
            json={"message": "   "},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
