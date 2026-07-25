"""Function route and repository-backed inventory availability tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.supply_chain import Inventory, Part, Warehouse
from app.repositories.function_repository import FunctionRepository


def test_function_route_uses_shared_envelope_and_preserves_request_id(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        headers={"X-Request-Id": "req-function-route"},
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["functionName"] == "getInventoryAvailability"
    assert body["data"]["warnings"] == []
    assert body["data"]["result"]["partId"] == "PART-B"
    assert body["meta"]["requestId"] == "req-function-route"
    assert response.headers["X-Request-Id"] == "req-function-route"


def test_function_route_returns_seeded_inventory_availability(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    result = response.json()["data"]["result"]
    assert result == {
        "partId": "PART-B",
        "totalAvailableQuantity": "100.00",
        "warehouses": [
            {
                "warehouseId": "CHI-01",
                "availableQuantity": "10.00",
                "reservedQuantity": "10.00",
            },
            {
                "warehouseId": "LAX-01",
                "availableQuantity": "10.00",
                "reservedQuantity": "10.00",
            },
            {
                "warehouseId": "SFO-01",
                "availableQuantity": "80.00",
                "reservedQuantity": "20.00",
            },
        ],
    }


def test_function_route_returns_structured_not_found_for_unknown_function(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/unknownFunction/execute",
        json={"parameters": {}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FUNCTION_NOT_FOUND"


def test_function_route_rejects_undeclared_top_level_fields(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={
            "parameters": {"partId": "PART-B"},
            "unexpected": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_function_route_rejects_missing_required_part_id(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FUNCTION_INPUT"


def test_function_route_rejects_invalid_part_id_type(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": 123}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FUNCTION_INPUT"


def test_function_route_rejects_invalid_part_id_value(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": ""}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FUNCTION_INPUT"


def test_inventory_availability_returns_part_not_found(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": "PART-DOES-NOT-EXIST"}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PART_NOT_FOUND"


def test_function_metadata_correctly_resolves_to_registered_handler(
    database_client: TestClient,
) -> None:
    response = database_client.get("/api/v1/ontology/functions/getInventoryAvailability")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["key"] == "getInventoryAvailability"
    assert body["handler"] == "getInventoryAvailability"
    assert body["inputModel"] == "GetInventoryAvailabilityParameters"
    assert body["outputModel"] == "InventoryAvailabilityResult"
    assert body["parameters"]["required"] == ["partId"]


def test_repository_uses_public_identifiers_not_relational_ids(
    database_session: Session,
    database_client: TestClient,
) -> None:
    part = database_session.execute(
        select(Part).where(Part.part_code == "PART-B")
    ).scalar_one()

    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": str(part.id)}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PART_NOT_FOUND"

    result = database_client.post(
        "/api/v1/functions/getInventoryAvailability/execute",
        json={"parameters": {"partId": "PART-B"}},
    ).json()["data"]["result"]
    assert result["warehouses"][0]["warehouseId"] == "CHI-01"
    assert result["warehouses"][0]["warehouseId"] != str(
        database_session.execute(
            select(Warehouse.id).where(Warehouse.warehouse_code == "CHI-01")
        ).scalar_one()
    )


def test_repository_returns_empty_warehouse_list_when_part_has_no_inventory_rows(
    database_session: Session,
) -> None:
    warehouse = database_session.execute(
        select(Warehouse).where(Warehouse.warehouse_code == "CHI-01")
    ).scalar_one()
    part = Part(
        part_code="PART-Z",
        name="Empty Inventory Part",
        category="Test",
        criticality="low",
        unit_cost=None,
        status="active",
    )
    database_session.add(part)
    database_session.flush()

    repository = FunctionRepository(database_session)
    assert repository.part_exists("PART-Z") is True
    assert repository.get_inventory_availability("PART-Z") == []

    inventory = database_session.execute(
        select(Inventory).where(
            Inventory.part_id == part.id,
            Inventory.warehouse_id == warehouse.id,
        )
    ).scalar_one_or_none()
    assert inventory is None
