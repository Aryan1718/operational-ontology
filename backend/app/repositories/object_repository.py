"""Repository helpers for generic ontology object retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidOntologyMappingError
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.models.risk import RiskEvent
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
from app.schemas.ontology import (
    OntologyObjectTypeDefinition,
    OntologyPropertyDefinition,
)

ModelType = type[Any]
_INVALID_LOOKUP = object()


OBJECT_TYPE_TO_MODEL: dict[str, ModelType] = {
    "CustomerOrder": CustomerOrder,
    "InventoryPosition": Inventory,
    "MitigationPlan": MitigationPlan,
    "MitigationStep": MitigationPlanStep,
    "OrderLine": CustomerOrderItem,
    "Part": Part,
    "Product": Product,
    "ProductPartRequirement": ProductBomItem,
    "PurchaseOrder": PurchaseOrder,
    "PurchaseOrderLine": PurchaseOrderItem,
    "RiskEvent": RiskEvent,
    "Shipment": Shipment,
    "Supplier": Supplier,
    "SupplierPart": SupplierPart,
    "Warehouse": Warehouse,
}


@dataclass(frozen=True, slots=True)
class ResolvedObjectMapping:
    """Validated model and identifier mapping for one ontology object type."""

    object_type: str
    model: ModelType
    identifier_property_key: str
    identifier_column: str
    title_property_key: str


class ObjectRepository:
    """Read operational records using trusted ontology mappings only."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_model_for_object_type(self, object_type: str) -> ModelType | None:
        """Return the explicitly supported SQLAlchemy model for one object type."""
        return OBJECT_TYPE_TO_MODEL.get(object_type)

    def resolve_object_mapping(
        self,
        definition: OntologyObjectTypeDefinition,
    ) -> ResolvedObjectMapping:
        """Validate one ontology object definition against the SQLAlchemy model."""
        model = self.get_model_for_object_type(definition.key)
        if model is None:
            raise InvalidOntologyMappingError(
                definition.key,
                f"Unsupported object type '{definition.key}' for object retrieval.",
            )

        model_table = getattr(model, "__tablename__", None)
        if definition.source.table != model_table:
            raise InvalidOntologyMappingError(
                definition.key,
                (
                    "Configured source table does not match "
                    "the expected SQLAlchemy model table."
                ),
            )

        self._require_mapped_column(
            definition=definition,
            model=model,
            column_name=definition.source.primaryKeyColumn,
            field_name="source primary key column",
        )
        model_primary_key_columns = {
            column.name for column in model.__table__.primary_key.columns
        }
        if definition.source.primaryKeyColumn not in model_primary_key_columns:
            raise InvalidOntologyMappingError(
                definition.key,
                (
                    "Configured source primary key column does not match "
                    "the SQLAlchemy model primary key."
                ),
            )

        identifier_property = self._get_property_definition(
            definition=definition,
            property_key=definition.primaryKeyProperty,
            field_name="identifier property",
        )
        self._require_mapped_column(
            definition=definition,
            model=model,
            column_name=identifier_property.sourceColumn,
            field_name="identifier column",
        )

        title_property = self._get_property_definition(
            definition=definition,
            property_key=definition.titleProperty,
            field_name="title property",
        )
        self._require_mapped_column(
            definition=definition,
            model=model,
            column_name=title_property.sourceColumn,
            field_name="title column",
        )

        for property_key, property_definition in definition.storedProperties.items():
            self._require_mapped_property_column(
                definition=definition,
                model=model,
                property_key=property_key,
                property_definition=property_definition,
            )

        for row_filter_column in (definition.source.rowFilter or {}):
            self._require_mapped_column(
                definition=definition,
                model=model,
                column_name=row_filter_column,
                field_name="row filter column",
            )

        return ResolvedObjectMapping(
            object_type=definition.key,
            model=model,
            identifier_property_key=definition.primaryKeyProperty,
            identifier_column=identifier_property.sourceColumn,
            title_property_key=definition.titleProperty,
        )

    def get_one(
        self,
        *,
        model: ModelType,
        identifier_column: str,
        object_id: str,
        row_filter: dict[str, Any] | None = None,
    ) -> Any | None:
        """Return one ORM record using only trusted model and column mappings."""
        lookup_value = self._coerce_lookup_value(model, identifier_column, object_id)
        if lookup_value is _INVALID_LOOKUP:
            return None

        statement = select(model).where(
            self._get_column(model, identifier_column) == lookup_value
        )
        for column_name, value in (row_filter or {}).items():
            statement = statement.where(self._get_column(model, column_name) == value)

        return self._session.execute(statement).scalar_one_or_none()

    def get_many_by_column(
        self,
        *,
        model: ModelType,
        filter_column: str,
        filter_value: Any,
        row_filter: dict[str, Any] | None = None,
        order_by_column: str,
    ) -> list[Any]:
        """Return multiple ORM records using trusted model and column mappings."""
        statement = select(model).where(self._get_column(model, filter_column) == filter_value)
        for column_name, value in (row_filter or {}).items():
            statement = statement.where(self._get_column(model, column_name) == value)
        statement = statement.order_by(self._get_column(model, order_by_column))
        return list(self._session.execute(statement).scalars().all())

    @staticmethod
    def get_column_attribute_name(model: ModelType, column_name: str) -> str:
        """Return the mapped ORM attribute name for one trusted table column."""
        return cast(str, ObjectRepository._get_column(model, column_name).key)

    @staticmethod
    def _get_column(model: ModelType, column_name: str) -> Any:
        column = model.__table__.columns.get(column_name)
        if column is None:
            raise KeyError(column_name)
        return column

    @staticmethod
    def _coerce_lookup_value(
        model: ModelType,
        column_name: str,
        raw_value: str,
    ) -> Any:
        column = ObjectRepository._get_column(model, column_name)
        try:
            python_type = column.type.python_type
        except (AttributeError, NotImplementedError):
            return raw_value

        if python_type is UUID:
            try:
                return UUID(raw_value)
            except ValueError:
                return _INVALID_LOOKUP

        if python_type is int:
            try:
                return int(raw_value)
            except ValueError:
                return _INVALID_LOOKUP

        return raw_value

    @staticmethod
    def _get_property_definition(
        *,
        definition: OntologyObjectTypeDefinition,
        property_key: str,
        field_name: str,
    ) -> OntologyPropertyDefinition:
        property_definition = definition.storedProperties.get(property_key)
        if property_definition is None:
            raise InvalidOntologyMappingError(
                definition.key,
                f"Missing {field_name} '{property_key}'.",
            )
        return property_definition

    def _require_mapped_property_column(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        model: ModelType,
        property_key: str,
        property_definition: OntologyPropertyDefinition,
    ) -> None:
        self._require_mapped_column(
            definition=definition,
            model=model,
            column_name=property_definition.sourceColumn,
            field_name=f"mapped column for property '{property_key}'",
        )

    def _require_mapped_column(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        model: ModelType,
        column_name: str,
        field_name: str,
    ) -> None:
        try:
            self._get_column(model, column_name)
        except KeyError as exc:
            raise InvalidOntologyMappingError(
                definition.key,
                f"Unknown {field_name} '{exc.args[0]}'.",
            ) from exc
