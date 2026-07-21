"""Ontology object route, runtime, and database integration tests."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_object_runtime
from app.core.exceptions import InvalidOntologyMappingError
from app.db.seed import _seed_uuid
from app.main import create_application
from app.ontology.loader import load_ontology_registry
from app.repositories.object_repository import ObjectRepository
from app.runtime.object_runtime import ObjectRuntime


def test_object_route_delegates_to_runtime() -> None:
    app = create_application()
    calls: list[tuple[str, str]] = []

    class StubRuntime:
        def get_object(self, object_type: str, object_id: str) -> dict[str, object]:
            calls.append((object_type, object_id))
            return {
                "objectType": object_type,
                "objectId": object_id,
                "displayName": "Stub Object",
                "properties": {"name": "Stub Object"},
            }

    app.dependency_overrides[get_object_runtime] = lambda: StubRuntime()

    with TestClient(app) as client:
        response = client.get("/api/v1/objects/Supplier/S-102")

    assert response.status_code == 200
    assert response.json()["data"]["objectId"] == "S-102"
    assert calls == [("Supplier", "S-102")]


def test_object_runtime_reads_supplier_from_real_seeded_database(
    database_session: Session,
) -> None:
    runtime = ObjectRuntime(
        registry=load_ontology_registry(),
        repository=ObjectRepository(database_session),
    )

    response = runtime.get_object("Supplier", "S-102")

    assert response.objectType == "Supplier"
    assert response.objectId == "S-102"
    assert response.displayName == "Vertex Electronics"
    assert response.properties == {
        "supplierId": _seed_uuid("supplier", "S-102"),
        "supplierCode": "S-102",
        "name": "Vertex Electronics",
        "country": "United States",
        "region": "West",
        "status": "active",
        "reliabilityScore": 72,
        "defaultLeadTimeDays": 5,
        "createdAt": datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        "updatedAt": datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc),
    }


def test_supplier_endpoint_returns_seeded_business_identifier(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/objects/Supplier/S-102")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "objectType": "Supplier",
        "objectId": "S-102",
        "displayName": "Vertex Electronics",
        "properties": {
            "supplierId": str(_seed_uuid("supplier", "S-102")),
            "supplierCode": "S-102",
            "name": "Vertex Electronics",
            "country": "United States",
            "region": "West",
            "status": "active",
            "reliabilityScore": "72.00",
            "defaultLeadTimeDays": 5,
            "createdAt": "2026-07-01T09:00:00Z",
            "updatedAt": "2026-07-14T08:00:00Z",
        },
    }


def test_part_endpoint_returns_seeded_business_identifier(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/objects/Part/PART-B")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["objectType"] == "Part"
    assert body["objectId"] == "PART-B"
    assert body["displayName"] == "Control Board"
    assert body["properties"] == {
        "partId": str(_seed_uuid("part", "PART-B")),
        "partCode": "PART-B",
        "name": "Control Board",
        "category": "Electronics",
        "criticality": "critical",
        "unitCost": None,
        "status": "active",
        "createdAt": "2026-07-01T09:15:00Z",
        "updatedAt": "2026-07-14T08:00:00Z",
    }


def test_object_route_returns_not_found_for_missing_business_identifier(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/objects/Supplier/S-DOES-NOT-EXIST")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "OBJECT_NOT_FOUND",
        "message": "Supplier object 'S-DOES-NOT-EXIST' was not found.",
        "details": {
            "objectType": "Supplier",
            "objectId": "S-DOES-NOT-EXIST",
        },
    }


def test_object_route_returns_unknown_object_type_error(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/objects/UnknownType/example")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "OBJECT_TYPE_NOT_FOUND",
        "message": "Ontology object type 'UnknownType' was not found.",
        "details": {"objectType": "UnknownType"},
    }


def test_object_route_returns_invalid_mapping_for_inventory_transfer(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/objects/InventoryTransfer/example")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INVALID_ONTOLOGY_MAPPING",
        "message": (
            "Ontology object type 'InventoryTransfer' has "
            "an invalid database mapping."
        ),
        "details": {
            "objectType": "InventoryTransfer",
            "reason": (
                "Unsupported object type 'InventoryTransfer' "
                "for object retrieval."
            ),
        },
    }


def test_object_runtime_invalid_mapping_uses_new_exception_code(
    database_session: Session,
) -> None:
    runtime = ObjectRuntime(
        registry=load_ontology_registry(),
        repository=ObjectRepository(database_session),
    )

    try:
        runtime.get_object("InventoryTransfer", "example")
    except InvalidOntologyMappingError as exc:
        assert exc.code == "INVALID_ONTOLOGY_MAPPING"
        assert exc.details["objectType"] == "InventoryTransfer"
    else:
        raise AssertionError("Expected invalid ontology mapping error")
