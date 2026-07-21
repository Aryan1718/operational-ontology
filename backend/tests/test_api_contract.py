"""Shared API contract tests for response envelopes and request IDs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import create_application


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def test_generated_request_id_is_returned_in_success_body_and_header(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/ontology")

    assert response.status_code == 200
    request_id = response.headers["X-Request-Id"]
    assert request_id
    assert response.json()["meta"]["requestId"] == request_id


def test_supplied_request_id_is_preserved_in_success_response(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/ontology",
        headers={"X-Request-Id": "req_client_success"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req_client_success"
    assert response.json()["meta"]["requestId"] == "req_client_success"


def test_supplied_request_id_is_preserved_in_error_response(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/ontology/object-types/UnknownType",
        headers={"X-Request-Id": "req_client_error"},
    )

    assert response.status_code == 404
    assert response.headers["X-Request-Id"] == "req_client_error"
    assert response.json()["meta"]["requestId"] == "req_client_error"


def test_generated_request_ids_differ_between_requests(client: TestClient) -> None:
    first = client.get("/api/v1/ontology")
    second = client.get("/api/v1/ontology")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Request-Id"] != second.headers["X-Request-Id"]


def test_success_response_includes_utc_timestamp(client: TestClient) -> None:
    response = client.get("/api/v1/ontology")

    assert response.status_code == 200
    _parse_utc_timestamp(response.json()["meta"]["timestamp"])


def test_error_response_includes_utc_timestamp(client: TestClient) -> None:
    response = client.get("/api/v1/ontology/object-types/UnknownType")

    assert response.status_code == 404
    _parse_utc_timestamp(response.json()["meta"]["timestamp"])


def test_validation_errors_use_structured_envelope() -> None:
    app = create_application()
    router = APIRouter()

    @router.get("/api/v1/test-validation/{item_id}")
    def read_validation_target(item_id: int) -> dict[str, int]:
        return {"itemId": item_id}

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/test-validation/not-an-int",
            headers={"X-Request-Id": "req_validation"},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert body["error"]["message"] == "The request is invalid."
    assert body["meta"]["requestId"] == "req_validation"
    assert response.headers["X-Request-Id"] == "req_validation"
    assert body["error"]["details"]["issues"]
    _parse_utc_timestamp(body["meta"]["timestamp"])


def test_unexpected_errors_use_internal_error_envelope_without_message_leak() -> None:
    app = create_application()
    router = APIRouter()

    @router.get("/api/v1/test-crash")
    def read_crash_target() -> dict[str, str]:
        raise RuntimeError("sensitive database failure")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/test-crash",
            headers={"X-Request-Id": "req_crash"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
        "details": {},
    }
    assert body["meta"]["requestId"] == "req_crash"
    assert response.headers["X-Request-Id"] == "req_crash"
    assert "sensitive database failure" not in response.text
    _parse_utc_timestamp(body["meta"]["timestamp"])


def test_openapi_documents_success_envelope_for_object_route(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    response_schema = schema["paths"]["/api/v1/objects/{object_type}/{object_id}"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    component_name = response_schema["$ref"].split("/")[-1]
    component = schema["components"]["schemas"][component_name]

    assert component["properties"]["data"]["$ref"].endswith("/OntologyObjectResponse")
    assert component["properties"]["meta"]["$ref"].endswith("/ResponseMeta")
