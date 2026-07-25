"""Function route and inventory availability integration tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed import _seed_uuid
from app.models.supply_chain import (
    Inventory,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    Warehouse,
)


def test_function_route_uses_shared_envelope_and_preserves_request_id(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        headers={"X-Request-Id": "req-function-route"},
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["functionName"] == "getInventoryAvailability"
    assert isinstance(body["data"]["result"], list)
    assert body["data"]["warnings"] == []
    assert body["meta"]["requestId"] == "req-function-route"
    assert response.headers["X-Request-Id"] == "req-function-route"


def test_function_route_returns_structured_not_found_for_unknown_function(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/unknownFunction",
        json={"parameters": {}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FUNCTION_NOT_FOUND"


def test_function_route_rejects_undeclared_top_level_fields(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
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
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FUNCTION_INPUT"


def test_function_route_rejects_undeclared_parameters(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-B",
                "unexpectedParameter": "x",
            }
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FUNCTION_INPUT"


def test_inventory_availability_uses_max_zero_for_available_quantity(
    database_client: TestClient,
    database_session: Session,
) -> None:
    part = database_session.execute(
        select(Part).where(Part.part_code == "PART-B")
    ).scalar_one()
    warehouse = Warehouse(
        id=_seed_uuid("warehouse", "WH-Z"),
        warehouse_code="WH-Z",
        name="Zero Floor Warehouse",
        city="Seattle",
        state=None,
        country="United States",
        region="West",
        status="active",
    )
    inventory = Inventory(
        id=_seed_uuid("inventory", "INV-WHZ-B"),
        warehouse_id=warehouse.id,
        item_type="part",
        part_id=part.id,
        product_id=None,
        on_hand_quantity=Decimal("5.00"),
        reserved_quantity=Decimal("10.00"),
        safety_stock_quantity=Decimal("1.00"),
    )
    database_session.add(warehouse)
    database_session.add(inventory)
    database_session.commit()

    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-B", "warehouseId": "WH-Z"}},
    )

    assert response.status_code == 200
    item = response.json()["data"]["result"][0]
    assert item["availableQuantity"] == "0.00"


def test_inventory_availability_filters_to_one_warehouse(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-B", "warehouseId": "SFO-01"}},
    )

    assert response.status_code == 200
    result = response.json()["data"]["result"]
    assert [item["warehouseId"] for item in result] == ["SFO-01"]
    assert result[0]["availableQuantity"] == "80.00"


def test_inventory_availability_returns_all_active_warehouses_when_unfiltered(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    result = response.json()["data"]["result"]
    assert [item["warehouseId"] for item in result] == ["SFO-01", "LAX-01", "CHI-01"]


def test_inventory_availability_excludes_inactive_warehouses(
    database_session: Session,
    database_client: TestClient,
) -> None:
    warehouse = database_session.execute(
        select(Warehouse).where(Warehouse.warehouse_code == "CHI-01")
    ).scalar_one()
    warehouse.status = "inactive"
    database_session.commit()

    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    result = response.json()["data"]["result"]
    assert [item["warehouseId"] for item in result] == ["SFO-01", "LAX-01"]


def test_inventory_availability_counts_inbound_on_exact_required_date_boundary(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-E",
                "warehouseId": "LAX-01",
                "requiredByDate": "2026-07-19",
            }
        },
    )

    assert response.status_code == 200
    item = response.json()["data"]["result"][0]
    assert item["eligibleInboundQuantity"] == "30.00"
    assert item["projectedAvailableByRequiredDate"] == "40.00"
    assert item["surplusAboveSafetyStock"] == "30.00"


def test_inventory_availability_excludes_inbound_after_required_date(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-E",
                "warehouseId": "LAX-01",
                "requiredByDate": "2026-07-18",
            }
        },
    )

    assert response.status_code == 200
    item = response.json()["data"]["result"][0]
    assert item["eligibleInboundQuantity"] == "0.00"
    assert item["projectedAvailableByRequiredDate"] == "10.00"


def test_inventory_availability_does_not_treat_in_transit_as_currently_available(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-E", "warehouseId": "LAX-01"}},
    )

    assert response.status_code == 200
    item = response.json()["data"]["result"][0]
    assert item["availableQuantity"] == "10.00"
    assert item["inTransitQuantity"] == "0.00"
    assert "projectedAvailableByRequiredDate" not in item or item[
        "projectedAvailableByRequiredDate"
    ] is None


def test_inventory_availability_does_not_double_count_transit_quantities(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-B",
                "warehouseId": "LAX-01",
                "requiredByDate": "2026-07-18",
            }
        },
    )

    assert response.status_code == 200
    item = response.json()["data"]["result"][0]
    assert item["availableQuantity"] == "10.00"
    assert item["eligibleInboundQuantity"] == "50.00"
    assert item["projectedAvailableByRequiredDate"] == "60.00"


def test_inventory_availability_returns_part_not_found(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-DOES-NOT-EXIST"}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PART_NOT_FOUND"


def test_inventory_availability_returns_warehouse_not_found(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-B",
                "warehouseId": "WH-DOES-NOT-EXIST",
            }
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WAREHOUSE_NOT_FOUND"


def test_inventory_availability_returns_empty_for_existing_warehouse_without_inventory(
    database_session: Session,
    database_client: TestClient,
) -> None:
    warehouse = Warehouse(
        id=_seed_uuid("warehouse", "WH-EMPTY"),
        warehouse_code="WH-EMPTY",
        name="Empty Warehouse",
        city="Dallas",
        state="TX",
        country="United States",
        region="Central",
        status="active",
    )
    database_session.add(warehouse)
    database_session.commit()

    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-B",
                "warehouseId": "WH-EMPTY",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["result"] == []


def test_inventory_availability_ordering_is_deterministic(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={"parameters": {"partId": "PART-B"}},
    )

    assert response.status_code == 200
    assert [item["warehouseId"] for item in response.json()["data"]["result"]] == [
        "SFO-01",
        "LAX-01",
        "CHI-01",
    ]


def test_inventory_availability_execution_does_not_mutate_operational_rows(
    database_session: Session,
    database_client: TestClient,
) -> None:
    before_inventory = list(
        database_session.execute(
            select(
                Inventory.id,
                Inventory.on_hand_quantity,
                Inventory.reserved_quantity,
                Inventory.safety_stock_quantity,
                Inventory.updated_at,
            )
        ).all()
    )
    before_purchase_order_items = list(
        database_session.execute(
            select(
                PurchaseOrderItem.id,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.quantity_received,
            )
        ).all()
    )
    before_purchase_orders = list(
        database_session.execute(
            select(
                PurchaseOrder.id,
                PurchaseOrder.status,
                PurchaseOrder.expected_delivery_date,
            )
        ).all()
    )

    response = database_client.post(
        "/api/v1/functions/getInventoryAvailability",
        json={
            "parameters": {
                "partId": "PART-B",
                "warehouseId": "LAX-01",
                "requiredByDate": "2026-07-18",
            }
        },
    )

    assert response.status_code == 200
    database_session.expire_all()

    after_inventory = list(
        database_session.execute(
            select(
                Inventory.id,
                Inventory.on_hand_quantity,
                Inventory.reserved_quantity,
                Inventory.safety_stock_quantity,
                Inventory.updated_at,
            )
        ).all()
    )
    after_purchase_order_items = list(
        database_session.execute(
            select(
                PurchaseOrderItem.id,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.quantity_received,
            )
        ).all()
    )
    after_purchase_orders = list(
        database_session.execute(
            select(
                PurchaseOrder.id,
                PurchaseOrder.status,
                PurchaseOrder.expected_delivery_date,
            )
        ).all()
    )

    assert after_inventory == before_inventory
    assert after_purchase_order_items == before_purchase_order_items
    assert after_purchase_orders == before_purchase_orders
