# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.audit_log import AuditLog
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.models.risk import RiskEvent, RiskEventImpact
from app.models.supply_chain import (
    CustomerOrder,
    CustomerOrderItem,
    Inventory,
    Part,
    Product,
    ProductBomItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Shipment,
    Supplier,
    SupplierPart,
    Warehouse,
)

SEED_REFERENCE_TIME = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
SEED_REFERENCE_DATE = date(2026, 7, 14)
SUPPLIER_CREATED_AT = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
PART_CREATED_AT = datetime(2026, 7, 1, 9, 15, tzinfo=timezone.utc)
PRODUCT_CREATED_AT = datetime(2026, 7, 1, 9, 30, tzinfo=timezone.utc)
WAREHOUSE_CREATED_AT = datetime(2026, 7, 1, 9, 45, tzinfo=timezone.utc)
COMMON_UPDATED_AT = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)
SUPPLIER_PART_CREATED_AT = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)
BOM_CREATED_AT = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
INVENTORY_UPDATED_AT = datetime(2026, 7, 14, 8, 30, tzinfo=timezone.utc)
ORDER_UPDATED_AT = datetime(2026, 7, 14, 8, 45, tzinfo=timezone.utc)
SHIPMENT_CREATED_AT = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
SHIPMENT_UPDATED_AT = datetime(2026, 7, 14, 8, 50, tzinfo=timezone.utc)
PURCHASE_ORDER_UPDATED_AT = datetime(2026, 7, 14, 8, 55, tzinfo=timezone.utc)
RISK_DETECTED_AT = datetime(2026, 7, 14, 9, 0, tzinfo=timezone.utc)
ZERO = Decimal("0.00")
ONE = Decimal("1.00")
TWO = Decimal("2.00")


class SeedProfile(StrEnum):
    BASE = "base"
    GOLDEN = "golden"


class SeedDriftError(RuntimeError):
    """Raised when an existing record does not match the deterministic fixture."""


@dataclass(slots=True)
class SeedResult:
    profile: str
    reference_time: datetime
    inserted_or_verified: dict[str, int]
    golden_risk_event_id: str | None
    checksum: str
    verification: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "referenceTime": self.reference_time.isoformat().replace("+00:00", "Z"),
            "insertedOrVerified": self.inserted_or_verified,
            "goldenRiskEventId": self.golden_risk_event_id,
            "checksum": self.checksum,
            "verification": self.verification,
        }


SUPPLIER_DATA = [
    {"code": "S-101", "name": "Northstar Components", "country": "United States", "region": "West", "status": "active", "reliability_score": Decimal("94.00"), "default_lead_time_days": 4},
    {"code": "S-102", "name": "Vertex Electronics", "country": "United States", "region": "West", "status": "active", "reliability_score": Decimal("72.00"), "default_lead_time_days": 5},
    {"code": "S-103", "name": "Midwest Power Systems", "country": "United States", "region": "Central", "status": "active", "reliability_score": Decimal("91.00"), "default_lead_time_days": 3},
]

PART_DATA = [
    {"code": "PART-A", "name": "Aluminum Housing", "category": "Mechanical", "criticality": "medium", "unit_cost": None, "status": "active"},
    {"code": "PART-B", "name": "Control Board", "category": "Electronics", "criticality": "critical", "unit_cost": None, "status": "active"},
    {"code": "PART-C", "name": "Power Cable", "category": "Electrical", "criticality": "medium", "unit_cost": None, "status": "active"},
    {"code": "PART-D", "name": "Battery Pack", "category": "Power", "criticality": "high", "unit_cost": None, "status": "active"},
    {"code": "PART-E", "name": "Sensor Module", "category": "Electronics", "criticality": "critical", "unit_cost": None, "status": "active"},
]

PRODUCT_DATA = [
    {"code": "PROD-100", "name": "Edge Controller", "category": "Industrial Control", "status": "active"},
    {"code": "PROD-200", "name": "Battery Gateway", "category": "Industrial Gateway", "status": "active"},
    {"code": "PROD-300", "name": "Vision Sensor", "category": "Machine Vision", "status": "active"},
]

WAREHOUSE_DATA = [
    {"code": "LAX-01", "seed_id": "WH-A", "name": "Los Angeles Fulfillment Center", "city": "Los Angeles", "state": None, "country": "United States", "region": "West", "status": "active"},
    {"code": "SFO-01", "seed_id": "WH-B", "name": "San Francisco Reserve Center", "city": "San Francisco", "state": None, "country": "United States", "region": "West", "status": "active"},
    {"code": "CHI-01", "seed_id": "WH-C", "name": "Chicago Distribution Center", "city": "Chicago", "state": None, "country": "United States", "region": "Central", "status": "active"},
]

SUPPLIER_PART_DATA = [
    ("SP-S102-A", "S-102", "PART-A", Decimal("45.00"), 5, Decimal("10.00"), False, "active"),
    ("SP-S102-B", "S-102", "PART-B", Decimal("100.00"), 5, Decimal("10.00"), True, "active"),
    ("SP-S102-C", "S-102", "PART-C", Decimal("12.00"), 4, Decimal("25.00"), False, "active"),
    ("SP-S102-D", "S-102", "PART-D", Decimal("140.00"), 5, Decimal("10.00"), False, "active"),
    ("SP-S102-E", "S-102", "PART-E", Decimal("80.00"), 5, Decimal("10.00"), True, "active"),
    ("SP-S103-D", "S-103", "PART-D", Decimal("145.00"), 3, Decimal("10.00"), True, "active"),
    ("SP-S101-A", "S-101", "PART-A", Decimal("47.00"), 4, Decimal("10.00"), True, "active"),
    ("SP-S101-C", "S-101", "PART-C", Decimal("13.00"), 4, Decimal("25.00"), True, "active"),
]

BOM_DATA = [
    ("BOM-P100-A", "PROD-100", "PART-A", ONE),
    ("BOM-P100-B", "PROD-100", "PART-B", ONE),
    ("BOM-P100-C", "PROD-100", "PART-C", TWO),
    ("BOM-P200-B", "PROD-200", "PART-B", ONE),
    ("BOM-P200-D", "PROD-200", "PART-D", ONE),
    ("BOM-P300-C", "PROD-300", "PART-C", ONE),
    ("BOM-P300-E", "PROD-300", "PART-E", ONE),
]
INVENTORY_DATA = [
    ("INV-WHA-A", "LAX-01", "PART-A", Decimal("120.00"), Decimal("20.00"), Decimal("20.00")),
    ("INV-WHA-B", "LAX-01", "PART-B", Decimal("20.00"), Decimal("10.00"), Decimal("30.00")),
    ("INV-WHA-C", "LAX-01", "PART-C", Decimal("200.00"), Decimal("40.00"), Decimal("20.00")),
    ("INV-WHA-D", "LAX-01", "PART-D", ZERO, ZERO, Decimal("15.00")),
    ("INV-WHA-E", "LAX-01", "PART-E", Decimal("20.00"), Decimal("10.00"), Decimal("10.00")),
    ("INV-WHB-A", "SFO-01", "PART-A", Decimal("50.00"), Decimal("10.00"), Decimal("20.00")),
    ("INV-WHB-B", "SFO-01", "PART-B", Decimal("100.00"), Decimal("20.00"), Decimal("30.00")),
    ("INV-WHB-C", "SFO-01", "PART-C", Decimal("80.00"), Decimal("10.00"), Decimal("20.00")),
    ("INV-WHB-D", "SFO-01", "PART-D", Decimal("20.00"), Decimal("5.00"), Decimal("15.00")),
    ("INV-WHB-E", "SFO-01", "PART-E", Decimal("10.00"), ZERO, Decimal("10.00")),
    ("INV-WHC-A", "CHI-01", "PART-A", Decimal("40.00"), Decimal("5.00"), Decimal("20.00")),
    ("INV-WHC-B", "CHI-01", "PART-B", Decimal("20.00"), Decimal("10.00"), Decimal("30.00")),
    ("INV-WHC-C", "CHI-01", "PART-C", Decimal("60.00"), Decimal("10.00"), Decimal("20.00")),
    ("INV-WHC-D", "CHI-01", "PART-D", Decimal("30.00"), Decimal("10.00"), Decimal("15.00")),
    ("INV-WHC-E", "CHI-01", "PART-E", Decimal("10.00"), ZERO, Decimal("10.00")),
]

ORDER_DATA = [
    ("ORD-881", "Apex Retail", "critical", "open", date(2026, 7, 10), date(2026, 7, 20)),
    ("ORD-882", "Metro Systems", "high", "open", date(2026, 7, 11), date(2026, 7, 21)),
    ("ORD-883", "Nova Vision", "normal", "open", date(2026, 7, 12), date(2026, 7, 22)),
    ("ORD-884", "Cancelled Control Order", "critical", "cancelled", date(2026, 7, 9), date(2026, 7, 19)),
]

ORDER_LINE_DATA = [
    ("OL-881-1", "ORD-881", "PROD-100", Decimal("40.00"), ZERO),
    ("OL-882-1", "ORD-882", "PROD-200", Decimal("10.00"), ZERO),
    ("OL-883-1", "ORD-883", "PROD-300", Decimal("50.00"), ZERO),
    ("OL-884-1", "ORD-884", "PROD-300", Decimal("100.00"), ZERO),
]

SHIPMENT_DATA = [
    ("SHIP-881", "ORD-881", "LAX-01", "planned", "Atlas Freight", date(2026, 7, 19), date(2026, 7, 21)),
    ("SHIP-882", "ORD-882", "LAX-01", "planned", "Atlas Freight", date(2026, 7, 20), date(2026, 7, 22)),
    ("SHIP-883", "ORD-883", "LAX-01", "planned", "Pacific Logistics", date(2026, 7, 21), date(2026, 7, 23)),
]

PURCHASE_ORDER_DATA = [
    ("PO-200", "S-102", "confirmed", date(2026, 7, 9), date(2026, 7, 19)),
    ("PO-201", "S-102", "confirmed", date(2026, 7, 8), date(2026, 7, 18)),
    ("PO-202", "S-102", "confirmed", date(2026, 7, 8), date(2026, 7, 18)),
    ("PO-203", "S-102", "confirmed", date(2026, 7, 8), date(2026, 7, 18)),
    ("PO-204", "S-102", "confirmed", date(2026, 7, 9), date(2026, 7, 19)),
    ("PO-205", "S-103", "confirmed", date(2026, 7, 10), date(2026, 7, 18)),
]

PURCHASE_ORDER_LINE_DATA = [
    ("POL-200-E", "PO-200", "PART-E", Decimal("30.00"), ZERO, Decimal("80.00")),
    ("POL-201-B", "PO-201", "PART-B", Decimal("50.00"), ZERO, Decimal("100.00")),
    ("POL-202-A", "PO-202", "PART-A", Decimal("20.00"), ZERO, Decimal("45.00")),
    ("POL-203-C", "PO-203", "PART-C", Decimal("50.00"), ZERO, Decimal("12.00")),
    ("POL-204-D", "PO-204", "PART-D", Decimal("10.00"), ZERO, Decimal("140.00")),
    ("POL-205-D", "PO-205", "PART-D", Decimal("10.00"), ZERO, Decimal("145.00")),
]

RISK_EVENT_DATA = {
    "code": "RISK-102",
    "risk_type": "supplier_delay",
    "supplier_code": "S-102",
    "severity": "high",
    "status": "open",
    "delay_days": 5,
    "description": "Supplier reported a five-day production delay.",
    "detected_at": RISK_DETECTED_AT,
    "created_at": RISK_DETECTED_AT,
    "updated_at": RISK_DETECTED_AT,
    "resolved_at": None,
}

EXPECTED_COUNTS = {
    SeedProfile.BASE: {"suppliers": 3, "parts": 5, "products": 3, "warehouses": 3, "supplierParts": 8, "productPartRequirements": 7, "inventoryPositions": 15, "customerOrders": 4, "orderLines": 4, "shipments": 3, "purchaseOrders": 6, "purchaseOrderLines": 6, "riskEvents": 0},
    SeedProfile.GOLDEN: {"suppliers": 3, "parts": 5, "products": 3, "warehouses": 3, "supplierParts": 8, "productPartRequirements": 7, "inventoryPositions": 15, "customerOrders": 4, "orderLines": 4, "shipments": 3, "purchaseOrders": 6, "purchaseOrderLines": 6, "riskEvents": 1},
}


def _seed_uuid(kind: str, code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"operational-ontology:{kind}:{code}")


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _assert_fields(model_name: str, code: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for field_name, expected_value in expected.items():
        if _normalize(actual[field_name]) != _normalize(expected_value):
            raise SeedDriftError(
                f"Seed drift for {model_name} {code}: field '{field_name}' expected "
                f"{_normalize(expected_value)!r} but found {_normalize(actual[field_name])!r}."
            )


def _get_one(session: Session, statement: Any) -> Any:
    return session.execute(statement).scalar_one_or_none()


def _seed_by_code(session: Session, model_name: str, model: Any, lookup_column: Any, code: str, expected: dict[str, Any]) -> Any:
    existing = _get_one(session, select(model).where(lookup_column == code))
    if existing is None:
        record = model(**expected)
        session.add(record)
        return record
    _assert_fields(model_name, code, {key: getattr(existing, key) for key in expected}, expected)
    return existing

def _reset_seed_data(session: Session, profile: SeedProfile) -> None:
    settings = get_settings()
    if settings.app_env.lower() == "production":
        raise RuntimeError("Refusing to reset deterministic seed data when APP_ENV=production.")
    if profile is SeedProfile.GOLDEN:
        session.execute(delete(RiskEvent).where(RiskEvent.risk_code == RISK_EVENT_DATA["code"]))

    purchase_order_ids = [_seed_uuid("purchase_order", code) for code, *_ in PURCHASE_ORDER_DATA]
    order_ids = [_seed_uuid("customer_order", code) for code, *_ in ORDER_DATA]
    warehouse_ids = [_seed_uuid("warehouse", record["seed_id"]) for record in WAREHOUSE_DATA]
    product_ids = [_seed_uuid("product", record["code"]) for record in PRODUCT_DATA]
    part_ids = [_seed_uuid("part", record["code"]) for record in PART_DATA]
    supplier_ids = [_seed_uuid("supplier", record["code"]) for record in SUPPLIER_DATA]

    session.execute(delete(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id.in_(purchase_order_ids)))
    session.execute(delete(PurchaseOrder).where(PurchaseOrder.id.in_(purchase_order_ids)))
    session.execute(delete(Shipment).where(Shipment.order_id.in_(order_ids)))
    session.execute(delete(CustomerOrderItem).where(CustomerOrderItem.order_id.in_(order_ids)))
    session.execute(delete(CustomerOrder).where(CustomerOrder.id.in_(order_ids)))
    session.execute(delete(Inventory).where(Inventory.warehouse_id.in_(warehouse_ids)))
    session.execute(delete(ProductBomItem).where(ProductBomItem.product_id.in_(product_ids)))
    session.execute(delete(SupplierPart).where(SupplierPart.supplier_id.in_(supplier_ids)))
    session.execute(delete(Warehouse).where(Warehouse.id.in_(warehouse_ids)))
    session.execute(delete(Product).where(Product.id.in_(product_ids)))
    session.execute(delete(Part).where(Part.id.in_(part_ids)))
    session.execute(delete(Supplier).where(Supplier.id.in_(supplier_ids)))


def _build_checksum_payload(profile: SeedProfile) -> list[dict[str, Any]]:
    payload = [
        {"table": "suppliers", "rows": SUPPLIER_DATA},
        {"table": "parts", "rows": PART_DATA},
        {"table": "products", "rows": PRODUCT_DATA},
        {"table": "warehouses", "rows": WAREHOUSE_DATA},
        {"table": "supplier_parts", "rows": SUPPLIER_PART_DATA},
        {"table": "product_bom_items", "rows": BOM_DATA},
        {"table": "inventory", "rows": INVENTORY_DATA},
        {"table": "customer_orders", "rows": ORDER_DATA},
        {"table": "customer_order_items", "rows": ORDER_LINE_DATA},
        {"table": "shipments", "rows": SHIPMENT_DATA},
        {"table": "purchase_orders", "rows": PURCHASE_ORDER_DATA},
        {"table": "purchase_order_items", "rows": PURCHASE_ORDER_LINE_DATA},
    ]
    if profile is SeedProfile.GOLDEN:
        payload.append({"table": "risk_events", "rows": [RISK_EVENT_DATA]})
    return payload


def _count_by_codes(session: Session, model: Any, column: Any, codes: list[str]) -> int:
    return session.execute(select(func.count()).select_from(model).where(column.in_(codes))).scalar_one()


def _verify_seed(session: Session, profile: SeedProfile) -> dict[str, Any]:
    counts = {
        "suppliers": _count_by_codes(session, Supplier, Supplier.supplier_code, [record["code"] for record in SUPPLIER_DATA]),
        "parts": _count_by_codes(session, Part, Part.part_code, [record["code"] for record in PART_DATA]),
        "products": _count_by_codes(session, Product, Product.product_code, [record["code"] for record in PRODUCT_DATA]),
        "warehouses": _count_by_codes(session, Warehouse, Warehouse.warehouse_code, [record["code"] for record in WAREHOUSE_DATA]),
        "supplierParts": session.execute(select(func.count()).select_from(SupplierPart)).scalar_one(),
        "productPartRequirements": session.execute(select(func.count()).select_from(ProductBomItem)).scalar_one(),
        "inventoryPositions": session.execute(select(func.count()).select_from(Inventory).where(Inventory.item_type == "part")).scalar_one(),
        "customerOrders": _count_by_codes(session, CustomerOrder, CustomerOrder.order_code, [code for code, *_ in ORDER_DATA]),
        "orderLines": session.execute(select(func.count()).select_from(CustomerOrderItem)).scalar_one(),
        "shipments": _count_by_codes(session, Shipment, Shipment.shipment_code, [code for code, *_ in SHIPMENT_DATA]),
        "purchaseOrders": _count_by_codes(session, PurchaseOrder, PurchaseOrder.purchase_order_code, [code for code, *_ in PURCHASE_ORDER_DATA]),
        "purchaseOrderLines": session.execute(select(func.count()).select_from(PurchaseOrderItem)).scalar_one(),
        "riskEvents": _count_by_codes(session, RiskEvent, RiskEvent.risk_code, [RISK_EVENT_DATA["code"]]),
    }
    for key, expected_value in EXPECTED_COUNTS[profile].items():
        if counts[key] != expected_value:
            raise RuntimeError(f"Seed verification failed for {key}: expected {expected_value}, found {counts[key]}.")

    transfer_check = session.execute(
        select(Inventory.on_hand_quantity, Inventory.reserved_quantity, Inventory.safety_stock_quantity)
        .join(Part, Inventory.part_id == Part.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .where(Part.part_code == "PART-B", Warehouse.warehouse_code == "SFO-01")
    ).one()
    transferable_quantity = transfer_check.on_hand_quantity - transfer_check.reserved_quantity - transfer_check.safety_stock_quantity
    if transferable_quantity != Decimal("50.00"):
        raise RuntimeError("Seed verification failed for WH-B / PART-B transferable quantity: expected 50.00.")

    relationships = {
        "supplierPartRowsWithSupplierAndPart": session.execute(select(func.count()).select_from(SupplierPart).join(Supplier, SupplierPart.supplier_id == Supplier.id).join(Part, SupplierPart.part_id == Part.id)).scalar_one(),
        "bomRowsWithProductAndPart": session.execute(select(func.count()).select_from(ProductBomItem).join(Product, ProductBomItem.product_id == Product.id).join(Part, ProductBomItem.part_id == Part.id)).scalar_one(),
        "inventoryRowsWithWarehouseAndPart": session.execute(select(func.count()).select_from(Inventory).join(Warehouse, Inventory.warehouse_id == Warehouse.id).join(Part, Inventory.part_id == Part.id).where(Inventory.item_type == "part")).scalar_one(),
        "orderLineRowsWithOrderAndProduct": session.execute(select(func.count()).select_from(CustomerOrderItem).join(CustomerOrder, CustomerOrderItem.order_id == CustomerOrder.id).join(Product, CustomerOrderItem.product_id == Product.id)).scalar_one(),
        "shipmentRowsWithOrderAndWarehouse": session.execute(select(func.count()).select_from(Shipment).join(CustomerOrder, Shipment.order_id == CustomerOrder.id).join(Warehouse, Shipment.warehouse_id == Warehouse.id)).scalar_one(),
        "purchaseOrderLineRowsWithOrderAndPart": session.execute(select(func.count()).select_from(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id).join(Part, PurchaseOrderItem.part_id == Part.id)).scalar_one(),
        "riskEventRowsWithSupplier": session.execute(select(func.count()).select_from(RiskEvent).join(Supplier, RiskEvent.supplier_id == Supplier.id).where(RiskEvent.risk_code == RISK_EVENT_DATA["code"])).scalar_one(),
    }
    expected_relationships = {
        "supplierPartRowsWithSupplierAndPart": 8,
        "bomRowsWithProductAndPart": 7,
        "inventoryRowsWithWarehouseAndPart": 15,
        "orderLineRowsWithOrderAndProduct": 4,
        "shipmentRowsWithOrderAndWarehouse": 3,
        "purchaseOrderLineRowsWithOrderAndPart": 6,
        "riskEventRowsWithSupplier": 1 if profile is SeedProfile.GOLDEN else 0,
    }
    for key, expected_value in expected_relationships.items():
        if relationships[key] != expected_value:
            raise RuntimeError(f"Seed relationship verification failed for {key}: expected {expected_value}, found {relationships[key]}.")

    workflow_tables = {
        "riskEventImpacts": session.execute(select(func.count()).select_from(RiskEventImpact)).scalar_one(),
        "mitigationPlans": session.execute(select(func.count()).select_from(MitigationPlan)).scalar_one(),
        "mitigationPlanSteps": session.execute(select(func.count()).select_from(MitigationPlanStep)).scalar_one(),
        "auditLogs": session.execute(select(func.count()).select_from(AuditLog)).scalar_one(),
    }
    for key, value in workflow_tables.items():
        if value != 0:
            raise RuntimeError(f"Seed verification failed: expected empty table {key}, found {value} rows.")

    return {
        "counts": counts,
        "relationships": relationships,
        "workflowTables": workflow_tables,
        "whbPartBTransferableQuantity": str(transferable_quantity),
        "referenceDate": SEED_REFERENCE_DATE.isoformat(),
    }

def seed_database(profile: SeedProfile, reset: bool = False) -> SeedResult:
    session_factory = get_session_factory()
    with session_factory() as session:
        with session.begin():
            if reset:
                _reset_seed_data(session, profile)

            suppliers = [
                _seed_by_code(session, "Supplier", Supplier, Supplier.supplier_code, record["code"], {
                    "id": _seed_uuid("supplier", record["code"]),
                    "supplier_code": record["code"],
                    "name": record["name"],
                    "country": record["country"],
                    "region": record["region"],
                    "status": record["status"],
                    "reliability_score": record["reliability_score"],
                    "default_lead_time_days": record["default_lead_time_days"],
                    "created_at": SUPPLIER_CREATED_AT,
                    "updated_at": COMMON_UPDATED_AT,
                })
                for record in SUPPLIER_DATA
            ]
            parts = [
                _seed_by_code(session, "Part", Part, Part.part_code, record["code"], {
                    "id": _seed_uuid("part", record["code"]),
                    "part_code": record["code"],
                    "name": record["name"],
                    "category": record["category"],
                    "criticality": record["criticality"],
                    "unit_cost": record["unit_cost"],
                    "status": record["status"],
                    "created_at": PART_CREATED_AT,
                    "updated_at": COMMON_UPDATED_AT,
                })
                for record in PART_DATA
            ]
            products = [
                _seed_by_code(session, "Product", Product, Product.product_code, record["code"], {
                    "id": _seed_uuid("product", record["code"]),
                    "product_code": record["code"],
                    "name": record["name"],
                    "category": record["category"],
                    "status": record["status"],
                    "created_at": PRODUCT_CREATED_AT,
                    "updated_at": COMMON_UPDATED_AT,
                })
                for record in PRODUCT_DATA
            ]
            warehouses = [
                _seed_by_code(session, "Warehouse", Warehouse, Warehouse.warehouse_code, record["code"], {
                    "id": _seed_uuid("warehouse", record["seed_id"]),
                    "warehouse_code": record["code"],
                    "name": record["name"],
                    "city": record["city"],
                    "state": record["state"],
                    "country": record["country"],
                    "region": record["region"],
                    "status": record["status"],
                    "created_at": WAREHOUSE_CREATED_AT,
                    "updated_at": COMMON_UPDATED_AT,
                })
                for record in WAREHOUSE_DATA
            ]

            supplier_code_to_id = {supplier.supplier_code: supplier.id for supplier in suppliers}
            part_code_to_id = {part.part_code: part.id for part in parts}
            product_code_to_id = {product.product_code: product.id for product in products}
            warehouse_code_to_id = {warehouse.warehouse_code: warehouse.id for warehouse in warehouses}

            for seed_id, supplier_code, part_code, unit_cost, lead_time_days, moq, preferred, status in SUPPLIER_PART_DATA:
                expected = {"id": _seed_uuid("supplier_part", seed_id), "supplier_id": supplier_code_to_id[supplier_code], "part_id": part_code_to_id[part_code], "supplier_part_code": seed_id, "is_primary_supplier": preferred, "lead_time_days": lead_time_days, "minimum_order_quantity": moq, "unit_cost": unit_cost, "status": status, "created_at": SUPPLIER_PART_CREATED_AT, "updated_at": COMMON_UPDATED_AT}
                existing = _get_one(session, select(SupplierPart).where(SupplierPart.supplier_id == expected["supplier_id"], SupplierPart.part_id == expected["part_id"]))
                if existing is None:
                    session.add(SupplierPart(**expected))
                else:
                    _assert_fields("SupplierPart", seed_id, {key: getattr(existing, key) for key in expected}, expected)

            for seed_id, product_code, part_code, quantity_required in BOM_DATA:
                expected = {"id": _seed_uuid("bom", seed_id), "product_id": product_code_to_id[product_code], "part_id": part_code_to_id[part_code], "quantity_required": quantity_required, "is_critical": True, "created_at": BOM_CREATED_AT, "updated_at": COMMON_UPDATED_AT}
                existing = _get_one(session, select(ProductBomItem).where(ProductBomItem.product_id == expected["product_id"], ProductBomItem.part_id == expected["part_id"]))
                if existing is None:
                    session.add(ProductBomItem(**expected))
                else:
                    _assert_fields("ProductBomItem", seed_id, {key: getattr(existing, key) for key in expected}, expected)

            for seed_id, warehouse_code, part_code, on_hand, reserved, safety_stock in INVENTORY_DATA:
                expected = {"id": _seed_uuid("inventory", seed_id), "warehouse_id": warehouse_code_to_id[warehouse_code], "item_type": "part", "part_id": part_code_to_id[part_code], "product_id": None, "on_hand_quantity": on_hand, "reserved_quantity": reserved, "safety_stock_quantity": safety_stock, "updated_at": INVENTORY_UPDATED_AT}
                existing = _get_one(session, select(Inventory).where(Inventory.warehouse_id == expected["warehouse_id"], Inventory.part_id == expected["part_id"], Inventory.item_type == "part"))
                if existing is None:
                    session.add(Inventory(**expected))
                else:
                    _assert_fields("Inventory", seed_id, {key: getattr(existing, key) for key in expected}, expected)

            orders: list[CustomerOrder] = []
            order_date_by_code: dict[str, date] = {}
            for code, customer_name, priority, status, order_date, requested_delivery_date in ORDER_DATA:
                order_date_by_code[code] = order_date
                orders.append(_seed_by_code(session, "CustomerOrder", CustomerOrder, CustomerOrder.order_code, code, {
                    "id": _seed_uuid("customer_order", code),
                    "order_code": code,
                    "customer_name": customer_name,
                    "priority": priority,
                    "status": status,
                    "requested_delivery_date": requested_delivery_date,
                    "created_at": datetime(order_date.year, order_date.month, order_date.day, 9, 0, tzinfo=timezone.utc),
                    "updated_at": ORDER_UPDATED_AT,
                }))
            order_code_to_id = {order.order_code: order.id for order in orders}
            for seed_id, order_code, product_code, quantity_ordered, quantity_allocated in ORDER_LINE_DATA:
                order_date = order_date_by_code[order_code]
                expected = {"id": _seed_uuid("customer_order_item", seed_id), "order_id": order_code_to_id[order_code], "product_id": product_code_to_id[product_code], "quantity_ordered": quantity_ordered, "quantity_allocated": quantity_allocated, "created_at": datetime(order_date.year, order_date.month, order_date.day, 9, 5, tzinfo=timezone.utc), "updated_at": ORDER_UPDATED_AT}
                existing = _get_one(session, select(CustomerOrderItem).where(CustomerOrderItem.id == expected["id"]))
                if existing is None:
                    session.add(CustomerOrderItem(**expected))
                else:
                    _assert_fields("CustomerOrderItem", seed_id, {key: getattr(existing, key) for key in expected}, expected)

            for code, order_code, warehouse_code, status, carrier, planned_ship_date, planned_delivery_date in SHIPMENT_DATA:
                _seed_by_code(session, "Shipment", Shipment, Shipment.shipment_code, code, {
                    "id": _seed_uuid("shipment", code),
                    "shipment_code": code,
                    "order_id": order_code_to_id[order_code],
                    "warehouse_id": warehouse_code_to_id[warehouse_code],
                    "status": status,
                    "carrier": carrier,
                    "tracking_number": None,
                    "planned_ship_date": planned_ship_date,
                    "actual_ship_date": None,
                    "planned_delivery_date": planned_delivery_date,
                    "actual_delivery_date": None,
                    "created_at": SHIPMENT_CREATED_AT,
                    "updated_at": SHIPMENT_UPDATED_AT,
                })

            purchase_orders: list[PurchaseOrder] = []
            purchase_order_date_by_code: dict[str, date] = {}
            for code, supplier_code, status, order_date, expected_delivery_date in PURCHASE_ORDER_DATA:
                purchase_order_date_by_code[code] = order_date
                purchase_orders.append(_seed_by_code(session, "PurchaseOrder", PurchaseOrder, PurchaseOrder.purchase_order_code, code, {
                    "id": _seed_uuid("purchase_order", code),
                    "purchase_order_code": code,
                    "supplier_id": supplier_code_to_id[supplier_code],
                    "status": status,
                    "order_date": order_date,
                    "expected_delivery_date": expected_delivery_date,
                    "actual_delivery_date": None,
                    "created_at": datetime(order_date.year, order_date.month, order_date.day, 10, 0, tzinfo=timezone.utc),
                    "updated_at": PURCHASE_ORDER_UPDATED_AT,
                }))
            purchase_order_code_to_id = {purchase_order.purchase_order_code: purchase_order.id for purchase_order in purchase_orders}

            for seed_id, purchase_order_code, part_code, quantity_ordered, quantity_received, unit_cost in PURCHASE_ORDER_LINE_DATA:
                order_date = purchase_order_date_by_code[purchase_order_code]
                expected = {"id": _seed_uuid("purchase_order_item", seed_id), "purchase_order_id": purchase_order_code_to_id[purchase_order_code], "part_id": part_code_to_id[part_code], "quantity_ordered": quantity_ordered, "quantity_received": quantity_received, "unit_cost": unit_cost, "created_at": datetime(order_date.year, order_date.month, order_date.day, 10, 0, tzinfo=timezone.utc), "updated_at": PURCHASE_ORDER_UPDATED_AT}
                existing = _get_one(session, select(PurchaseOrderItem).where(PurchaseOrderItem.id == expected["id"]))
                if existing is None:
                    session.add(PurchaseOrderItem(**expected))
                else:
                    _assert_fields("PurchaseOrderItem", seed_id, {key: getattr(existing, key) for key in expected}, expected)

            if profile is SeedProfile.GOLDEN:
                _seed_by_code(session, "RiskEvent", RiskEvent, RiskEvent.risk_code, RISK_EVENT_DATA["code"], {
                    "id": _seed_uuid("risk_event", RISK_EVENT_DATA["code"]),
                    "risk_code": RISK_EVENT_DATA["code"],
                    "risk_type": RISK_EVENT_DATA["risk_type"],
                    "severity": RISK_EVENT_DATA["severity"],
                    "status": RISK_EVENT_DATA["status"],
                    "supplier_id": supplier_code_to_id[RISK_EVENT_DATA["supplier_code"]],
                    "part_id": None,
                    "warehouse_id": None,
                    "shipment_id": None,
                    "delay_days": RISK_EVENT_DATA["delay_days"],
                    "description": RISK_EVENT_DATA["description"],
                    "detected_at": RISK_EVENT_DATA["detected_at"],
                    "created_at": RISK_EVENT_DATA["created_at"],
                    "updated_at": RISK_EVENT_DATA["updated_at"],
                    "resolved_at": RISK_EVENT_DATA["resolved_at"],
                })
            else:
                existing_risk = _get_one(session, select(RiskEvent).where(RiskEvent.risk_code == RISK_EVENT_DATA["code"]))
                if existing_risk is not None:
                    raise SeedDriftError("Base profile expects no RISK-102 record, but one already exists. Use the golden profile or run with --reset in a non-production environment.")

        verification = _verify_seed(session, profile)

    checksum = hashlib.sha256(json.dumps(_normalize(_build_checksum_payload(profile)), sort_keys=True).encode("utf-8")).hexdigest()
    return SeedResult(profile=profile.value, reference_time=SEED_REFERENCE_TIME, inserted_or_verified=EXPECTED_COUNTS[profile], golden_risk_event_id=RISK_EVENT_DATA["code"] if profile is SeedProfile.GOLDEN else None, checksum=checksum, verification=verification)


def run_seed(profile: str = SeedProfile.GOLDEN.value, reset: bool = False) -> SeedResult:
    return seed_database(SeedProfile(profile), reset=reset)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic supply-chain data.")
    parser.add_argument("--profile", choices=[profile.value for profile in SeedProfile], default=SeedProfile.GOLDEN.value, help="Seed profile to load.")
    parser.add_argument("--reset", action="store_true", help="Delete the deterministic fixture rows before reseeding. Blocked in production.")
    args = parser.parse_args()
    result = run_seed(profile=args.profile, reset=args.reset)
    print(json.dumps(result.as_dict(), indent=2))


if __name__ == "__main__":
    main()

