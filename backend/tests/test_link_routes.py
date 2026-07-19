"""Ontology link route, runtime, and database integration tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_link_runtime
from app.core.exceptions import InvalidOntologyMappingError, LinkNotFoundError
from app.db.seed import _seed_uuid
from app.main import create_application
from app.ontology.loader import load_ontology_registry
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository, ResolvedObjectMapping
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.ontology import OntologyLinkTypeDefinition, OntologyObjectTypeDefinition


class _StubRegistry:
    def __init__(
        self,
        *,
        object_definitions: dict[str, OntologyObjectTypeDefinition],
        link_definitions: dict[str, OntologyLinkTypeDefinition],
    ) -> None:
        self._object_definitions = object_definitions
        self._link_definitions = link_definitions

    def get_object_type(self, object_type: str) -> OntologyObjectTypeDefinition | None:
        return self._object_definitions.get(object_type)

    def get_link_type(self, link_type: str) -> OntologyLinkTypeDefinition | None:
        return self._link_definitions.get(link_type)


class _StubRepository:
    def __init__(
        self,
        *,
        mappings: dict[str, ResolvedObjectMapping],
        records_by_lookup: dict[tuple[type[object], str], object | None],
        linked_records: dict[tuple[type[object], str, object, tuple[tuple[str, object], ...], str], list[object]],
        column_attribute_names: dict[tuple[type[object], str], str],
    ) -> None:
        self._mappings = mappings
        self._records_by_lookup = records_by_lookup
        self._linked_records = linked_records
        self._column_attribute_names = column_attribute_names
        self.get_many_calls: list[dict[str, object]] = []

    def resolve_object_mapping(
        self,
        definition: OntologyObjectTypeDefinition,
    ) -> ResolvedObjectMapping:
        return self._mappings[definition.key]

    def get_one(
        self,
        *,
        model: type[object],
        identifier_column: str,
        object_id: str,
        row_filter: dict[str, object] | None = None,
    ) -> object | None:
        del identifier_column, row_filter
        return self._records_by_lookup.get((model, object_id))

    def get_many_by_column(
        self,
        *,
        model: type[object],
        filter_column: str,
        filter_value: object,
        row_filter: dict[str, object] | None = None,
        order_by_column: str,
    ) -> list[object]:
        normalized_row_filter = tuple(sorted((row_filter or {}).items()))
        self.get_many_calls.append(
            {
                "model": model,
                "filterColumn": filter_column,
                "filterValue": filter_value,
                "rowFilter": dict(normalized_row_filter),
                "orderByColumn": order_by_column,
            }
        )
        return self._linked_records[
            (model, filter_column, filter_value, normalized_row_filter, order_by_column)
        ]

    def get_column_attribute_name(self, model: type[object], column_name: str) -> str:
        key = (model, column_name)
        if key not in self._column_attribute_names:
            raise KeyError(column_name)
        return self._column_attribute_names[key]


class _SourceModel:
    pass


class _TargetModel:
    pass


def _stored_property(source_column: str) -> dict[str, object]:
    return {
        "sourceColumn": source_column,
        "type": "string",
        "required": True,
        "readOnly": True,
    }


def _object_definition(
    *,
    key: str,
    table: str,
    primary_key_property: str,
    title_property: str,
    stored_properties: dict[str, dict[str, object]],
    links: list[str],
) -> OntologyObjectTypeDefinition:
    return OntologyObjectTypeDefinition.model_validate(
        {
            "key": key,
            "displayName": key,
            "source": {"table": table, "primaryKeyColumn": "id"},
            "primaryKeyProperty": primary_key_property,
            "titleProperty": title_property,
            "storedProperties": stored_properties,
            "links": links,
        }
    )


def _link_definition(
    *,
    key: str,
    kind: str = "stored",
    source_object_type: str,
    target_object_type: str,
    source_join_property: str | None,
    target_join_property: str | None,
    storage_table: str | None = "target_objects",
    storage_column: str | None = "source_code",
) -> OntologyLinkTypeDefinition:
    payload: dict[str, Any] = {
        "key": key,
        "displayName": key,
        "kind": kind,
        "sourceObjectType": source_object_type,
        "targetObjectType": target_object_type,
        "cardinality": "one-to-many",
        "direction": "outbound",
        "sourceJoinProperty": source_join_property,
        "targetJoinProperty": target_join_property,
        "path": [],
    }
    if storage_table is not None and storage_column is not None:
        payload["storage"] = {
            "table": storage_table,
            "sourceColumn": storage_column,
            "rowFilter": {"status": "active"},
        }
    else:
        payload["storage"] = None
    return OntologyLinkTypeDefinition.model_validate(payload)


def _runtime_for_synthetic_link(
    *,
    source_definition: OntologyObjectTypeDefinition,
    target_definition: OntologyObjectTypeDefinition,
    link_definition: OntologyLinkTypeDefinition,
    source_record: object | None = None,
    target_records: list[object] | None = None,
    source_identifier_column: str = "source_code",
    target_identifier_column: str = "target_code",
    source_columns: dict[str, str] | None = None,
    target_columns: dict[str, str] | None = None,
) -> tuple[LinkRuntime, _StubRepository]:
    source_mapping = ResolvedObjectMapping(
        object_type=source_definition.key,
        model=_SourceModel,
        identifier_property_key=source_definition.primaryKeyProperty,
        identifier_column=source_identifier_column,
        title_property_key=source_definition.titleProperty,
    )
    target_mapping = ResolvedObjectMapping(
        object_type=target_definition.key,
        model=_TargetModel,
        identifier_property_key=target_definition.primaryKeyProperty,
        identifier_column=target_identifier_column,
        title_property_key=target_definition.titleProperty,
    )
    source_columns = source_columns or {
        "id": "id",
        "source_code": "source_code",
        "name": "name",
    }
    target_columns = target_columns or {
        "id": "id",
        "target_code": "target_code",
        "source_code": "source_code",
        "status": "status",
        "name": "name",
    }
    repository = _StubRepository(
        mappings={source_definition.key: source_mapping, target_definition.key: target_mapping},
        records_by_lookup={(_SourceModel, "SRC-1"): source_record or SimpleNamespace(id="db-source-1", source_code="SRC-1", name="Source 1")},
        linked_records={
            (_TargetModel, "source_code", "SRC-1", (("status", "active"),), target_identifier_column): target_records
            or [SimpleNamespace(id="db-target-1", target_code="TARGET-1", source_code="SRC-1", status="active", name="Target 1")]
        },
        column_attribute_names={
            **{(_SourceModel, key): value for key, value in source_columns.items()},
            **{(_TargetModel, key): value for key, value in target_columns.items()},
        },
    )
    registry = cast(
        OntologyRegistry,
        _StubRegistry(
            object_definitions={
                source_definition.key: source_definition,
                target_definition.key: target_definition,
            },
            link_definitions={link_definition.key: link_definition},
        ),
    )
    object_runtime = ObjectRuntime(
        registry=registry,
        repository=cast(ObjectRepository, repository),
    )
    runtime = LinkRuntime(
        registry=registry,
        repository=cast(ObjectRepository, repository),
        object_runtime=object_runtime,
    )
    return runtime, repository


def test_link_route_delegates_to_runtime() -> None:
    app = create_application()
    calls: list[tuple[str, str, str]] = []

    class StubRuntime:
        def get_linked_objects(
            self,
            object_type: str,
            object_id: str,
            link_type: str,
        ) -> dict[str, object]:
            calls.append((object_type, object_id, link_type))
            return {
                "source": {"objectType": object_type, "objectId": object_id},
                "linkType": link_type,
                "targetObjectType": "TargetObject",
                "cardinality": "one-to-many",
                "objects": [],
            }

    app.dependency_overrides[get_link_runtime] = lambda: StubRuntime()

    with TestClient(app) as client:
        response = client.get("/api/v1/objects/Supplier/S-102/links/supplierToPurchaseOrders")

    assert response.status_code == 200
    assert response.json() == {
        "source": {"objectType": "Supplier", "objectId": "S-102"},
        "linkType": "supplierToPurchaseOrders",
        "targetObjectType": "TargetObject",
        "cardinality": "one-to-many",
        "objects": [],
    }
    assert calls == [("Supplier", "S-102", "supplierToPurchaseOrders")]


def test_link_runtime_rejects_link_with_source_mismatch_even_if_declared() -> None:
    source_definition = _object_definition(
        key="SyntheticSource",
        table="source_objects",
        primary_key_property="sourceCode",
        title_property="name",
        stored_properties={
            "sourceId": _stored_property("id"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
        },
        links=["syntheticLink"],
    )
    target_definition = _object_definition(
        key="SyntheticTarget",
        table="target_objects",
        primary_key_property="targetCode",
        title_property="name",
        stored_properties={
            "targetId": _stored_property("id"),
            "targetCode": _stored_property("target_code"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
            "status": _stored_property("status"),
        },
        links=[],
    )
    link_definition = _link_definition(
        key="syntheticLink",
        source_object_type="DifferentSource",
        target_object_type="SyntheticTarget",
        source_join_property="sourceCode",
        target_join_property="sourceCode",
    )
    runtime, _ = _runtime_for_synthetic_link(
        source_definition=source_definition,
        target_definition=target_definition,
        link_definition=link_definition,
    )

    try:
        runtime.get_linked_objects("SyntheticSource", "SRC-1", "syntheticLink")
    except LinkNotFoundError as exc:
        assert exc.code == "LINK_NOT_FOUND"
        assert exc.details == {"objectType": "SyntheticSource", "linkType": "syntheticLink"}
    else:
        raise AssertionError("Expected link-not-found error")


def test_link_runtime_rejects_missing_source_join_property_mapping() -> None:
    source_definition = _object_definition(
        key="SyntheticSource",
        table="source_objects",
        primary_key_property="sourceCode",
        title_property="name",
        stored_properties={
            "sourceId": _stored_property("id"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
        },
        links=["syntheticLink"],
    )
    target_definition = _object_definition(
        key="SyntheticTarget",
        table="target_objects",
        primary_key_property="targetCode",
        title_property="name",
        stored_properties={
            "targetId": _stored_property("id"),
            "targetCode": _stored_property("target_code"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
            "status": _stored_property("status"),
        },
        links=[],
    )
    runtime, _ = _runtime_for_synthetic_link(
        source_definition=source_definition,
        target_definition=target_definition,
        link_definition=_link_definition(
            key="syntheticLink",
            source_object_type="SyntheticSource",
            target_object_type="SyntheticTarget",
            source_join_property=None,
            target_join_property="sourceCode",
        ),
    )

    try:
        runtime.get_linked_objects("SyntheticSource", "SRC-1", "syntheticLink")
    except InvalidOntologyMappingError as exc:
        assert exc.code == "INVALID_ONTOLOGY_MAPPING"
        assert "missing source join property mapping" in cast(str, exc.details["reason"]).lower()
    else:
        raise AssertionError("Expected invalid ontology mapping error")


def test_link_runtime_rejects_missing_target_join_property_mapping() -> None:
    source_definition = _object_definition(
        key="SyntheticSource",
        table="source_objects",
        primary_key_property="sourceCode",
        title_property="name",
        stored_properties={
            "sourceId": _stored_property("id"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
        },
        links=["syntheticLink"],
    )
    target_definition = _object_definition(
        key="SyntheticTarget",
        table="target_objects",
        primary_key_property="targetCode",
        title_property="name",
        stored_properties={
            "targetId": _stored_property("id"),
            "targetCode": _stored_property("target_code"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
            "status": _stored_property("status"),
        },
        links=[],
    )
    runtime, _ = _runtime_for_synthetic_link(
        source_definition=source_definition,
        target_definition=target_definition,
        link_definition=_link_definition(
            key="syntheticLink",
            source_object_type="SyntheticSource",
            target_object_type="SyntheticTarget",
            source_join_property="sourceCode",
            target_join_property=None,
        ),
    )

    try:
        runtime.get_linked_objects("SyntheticSource", "SRC-1", "syntheticLink")
    except InvalidOntologyMappingError as exc:
        assert exc.code == "INVALID_ONTOLOGY_MAPPING"
        assert "missing target join property mapping" in cast(str, exc.details["reason"]).lower()
    else:
        raise AssertionError("Expected invalid ontology mapping error")


def test_link_runtime_rejects_invalid_target_column_mapping() -> None:
    source_definition = _object_definition(
        key="SyntheticSource",
        table="source_objects",
        primary_key_property="sourceCode",
        title_property="name",
        stored_properties={
            "sourceId": _stored_property("id"),
            "sourceCode": _stored_property("source_code"),
            "name": _stored_property("name"),
        },
        links=["syntheticLink"],
    )
    target_definition = _object_definition(
        key="SyntheticTarget",
        table="target_objects",
        primary_key_property="targetCode",
        title_property="name",
        stored_properties={
            "targetId": _stored_property("id"),
            "targetCode": _stored_property("target_code"),
            "sourceCode": _stored_property("missing_source_column"),
            "name": _stored_property("name"),
            "status": _stored_property("status"),
        },
        links=[],
    )
    runtime, _ = _runtime_for_synthetic_link(
        source_definition=source_definition,
        target_definition=target_definition,
        link_definition=_link_definition(
            key="syntheticLink",
            source_object_type="SyntheticSource",
            target_object_type="SyntheticTarget",
            source_join_property="sourceCode",
            target_join_property="sourceCode",
            storage_column="missing_source_column",
        ),
    )

    try:
        runtime.get_linked_objects("SyntheticSource", "SRC-1", "syntheticLink")
    except InvalidOntologyMappingError as exc:
        assert exc.code == "INVALID_ONTOLOGY_MAPPING"
        assert exc.details["objectType"] == "SyntheticTarget"
        assert exc.details["reason"] == "Unknown stored link column 'missing_source_column'."
    else:
        raise AssertionError("Expected invalid ontology mapping error")


def test_supplier_to_purchase_orders_returns_ordered_linked_objects(
    database_session: Session,
) -> None:
    runtime = LinkRuntime(
        registry=load_ontology_registry(),
        repository=ObjectRepository(database_session),
        object_runtime=ObjectRuntime(
            registry=load_ontology_registry(),
            repository=ObjectRepository(database_session),
        ),
    )

    response = runtime.get_linked_objects(
        "Supplier",
        "S-102",
        "supplierToPurchaseOrders",
    )

    assert response.source.objectType == "Supplier"
    assert response.source.objectId == "S-102"
    assert response.linkType == "supplierToPurchaseOrders"
    assert response.targetObjectType == "PurchaseOrder"
    assert response.cardinality == "one-to-many"
    assert [item.objectId for item in response.objects] == [
        "PO-200",
        "PO-201",
        "PO-202",
        "PO-203",
        "PO-204",
    ]


def test_supplier_part_to_supplier_uses_target_primary_key_property(
    database_session: Session,
) -> None:
    supplier_part_id = str(_seed_uuid("supplier_part", "SP-S102-B"))
    runtime = LinkRuntime(
        registry=load_ontology_registry(),
        repository=ObjectRepository(database_session),
        object_runtime=ObjectRuntime(
            registry=load_ontology_registry(),
            repository=ObjectRepository(database_session),
        ),
    )

    response = runtime.get_linked_objects(
        "SupplierPart",
        supplier_part_id,
        "supplierPartToSupplier",
    )

    assert response.source.objectType == "SupplierPart"
    assert response.source.objectId == supplier_part_id
    assert response.objects[0].objectType == "Supplier"
    assert response.objects[0].objectId == "S-102"
    assert response.objects[0].properties["supplierId"] != response.objects[0].objectId


def test_warehouse_to_shipments_returns_empty_objects_array(
    database_session: Session,
) -> None:
    runtime = LinkRuntime(
        registry=load_ontology_registry(),
        repository=ObjectRepository(database_session),
        object_runtime=ObjectRuntime(
            registry=load_ontology_registry(),
            repository=ObjectRepository(database_session),
        ),
    )

    response = runtime.get_linked_objects(
        "Warehouse",
        "CHI-01",
        "warehouseToShipments",
    )

    assert response.source.objectType == "Warehouse"
    assert response.source.objectId == "CHI-01"
    assert response.objects == []


def test_link_route_returns_existing_success_shape(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/Supplier/S-102/links/supplierToPurchaseOrders"
    )

    assert response.status_code == 200
    assert response.json() == {
        "source": {"objectType": "Supplier", "objectId": "S-102"},
        "linkType": "supplierToPurchaseOrders",
        "targetObjectType": "PurchaseOrder",
        "cardinality": "one-to-many",
        "objects": [
            {
                "objectType": "PurchaseOrder",
                "objectId": "PO-200",
                "displayName": "PO-200",
                "properties": {
                    "purchaseOrderId": str(_seed_uuid("purchase_order", "PO-200")),
                    "purchaseOrderCode": "PO-200",
                    "supplierId": str(_seed_uuid("supplier", "S-102")),
                    "status": "confirmed",
                    "orderDate": "2026-07-09",
                    "expectedDeliveryDate": "2026-07-19",
                    "actualDeliveryDate": None,
                    "createdAt": "2026-07-09T10:00:00Z",
                    "updatedAt": "2026-07-14T08:55:00Z",
                },
            },
            {
                "objectType": "PurchaseOrder",
                "objectId": "PO-201",
                "displayName": "PO-201",
                "properties": {
                    "purchaseOrderId": str(_seed_uuid("purchase_order", "PO-201")),
                    "purchaseOrderCode": "PO-201",
                    "supplierId": str(_seed_uuid("supplier", "S-102")),
                    "status": "confirmed",
                    "orderDate": "2026-07-08",
                    "expectedDeliveryDate": "2026-07-18",
                    "actualDeliveryDate": None,
                    "createdAt": "2026-07-08T10:00:00Z",
                    "updatedAt": "2026-07-14T08:55:00Z",
                },
            },
            {
                "objectType": "PurchaseOrder",
                "objectId": "PO-202",
                "displayName": "PO-202",
                "properties": {
                    "purchaseOrderId": str(_seed_uuid("purchase_order", "PO-202")),
                    "purchaseOrderCode": "PO-202",
                    "supplierId": str(_seed_uuid("supplier", "S-102")),
                    "status": "confirmed",
                    "orderDate": "2026-07-08",
                    "expectedDeliveryDate": "2026-07-18",
                    "actualDeliveryDate": None,
                    "createdAt": "2026-07-08T10:00:00Z",
                    "updatedAt": "2026-07-14T08:55:00Z",
                },
            },
            {
                "objectType": "PurchaseOrder",
                "objectId": "PO-203",
                "displayName": "PO-203",
                "properties": {
                    "purchaseOrderId": str(_seed_uuid("purchase_order", "PO-203")),
                    "purchaseOrderCode": "PO-203",
                    "supplierId": str(_seed_uuid("supplier", "S-102")),
                    "status": "confirmed",
                    "orderDate": "2026-07-08",
                    "expectedDeliveryDate": "2026-07-18",
                    "actualDeliveryDate": None,
                    "createdAt": "2026-07-08T10:00:00Z",
                    "updatedAt": "2026-07-14T08:55:00Z",
                },
            },
            {
                "objectType": "PurchaseOrder",
                "objectId": "PO-204",
                "displayName": "PO-204",
                "properties": {
                    "purchaseOrderId": str(_seed_uuid("purchase_order", "PO-204")),
                    "purchaseOrderCode": "PO-204",
                    "supplierId": str(_seed_uuid("supplier", "S-102")),
                    "status": "confirmed",
                    "orderDate": "2026-07-09",
                    "expectedDeliveryDate": "2026-07-19",
                    "actualDeliveryDate": None,
                    "createdAt": "2026-07-09T10:00:00Z",
                    "updatedAt": "2026-07-14T08:55:00Z",
                },
            },
        ],
    }


def test_link_route_returns_unknown_object_type_error(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/UnknownType/example/links/supplierToPurchaseOrders"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "OBJECT_TYPE_NOT_FOUND",
            "message": "Ontology object type 'UnknownType' was not found.",
            "details": {"objectType": "UnknownType"},
        }
    }


def test_link_route_returns_missing_source_object_error(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/Supplier/S-DOES-NOT-EXIST/links/supplierToPurchaseOrders"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "OBJECT_NOT_FOUND",
            "message": "Supplier object 'S-DOES-NOT-EXIST' was not found.",
            "details": {
                "objectType": "Supplier",
                "objectId": "S-DOES-NOT-EXIST",
            },
        }
    }


def test_link_route_returns_unknown_link_type_error(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/Supplier/S-102/links/unknownLink"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "LINK_NOT_FOUND",
            "message": (
                "Ontology link type 'unknownLink' was not found for object type 'Supplier'."
            ),
            "details": {"objectType": "Supplier", "linkType": "unknownLink"},
        }
    }


def test_link_route_rejects_globally_valid_link_not_declared_on_source_type(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/Supplier/S-102/links/customerOrderToOrderLines"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "LINK_NOT_FOUND",
            "message": (
                "Ontology link type 'customerOrderToOrderLines' was not found for object type 'Supplier'."
            ),
            "details": {
                "objectType": "Supplier",
                "linkType": "customerOrderToOrderLines",
            },
        }
    }


def test_link_route_rejects_unsupported_flattened_link(
    database_client: TestClient,
) -> None:
    response = database_client.get(
        "/api/v1/objects/Supplier/S-102/links/supplierSuppliesParts"
    )

    assert response.status_code == 501
    assert response.json() == {
        "error": {
            "code": "LINK_RESOLUTION_NOT_IMPLEMENTED",
            "message": (
                "Ontology link type 'supplierSuppliesParts' uses unsupported link kind 'flattened'."
            ),
            "details": {"linkType": "supplierSuppliesParts", "kind": "flattened"},
        }
    }

