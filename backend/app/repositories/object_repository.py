"""Repository helpers for generic ontology object retrieval."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Sequence, cast
from uuid import UUID

from sqlalchemy import String, cast as sa_cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidOntologyMappingError, InvalidRequestError
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


@dataclass(frozen=True, slots=True)
class RepositorySearchFilter:
    """Validated repository filter bound to one trusted model column."""

    property_key: str
    column_name: str
    operator: str
    value: Any


@dataclass(frozen=True, slots=True)
class RepositorySearchSort:
    """Validated repository sort bound to one trusted model column."""

    property_key: str
    column_name: str
    direction: str


@dataclass(frozen=True, slots=True)
class SearchResultPage:
    """Repository search page plus opaque pagination state."""

    records: list[Any]
    next_cursor: str | None
    has_more: bool


class ObjectSearchCursorCodec:
    """Opaque offset cursor codec for single-object search pages."""

    _VERSION = 1

    @classmethod
    def encode(cls, offset: int) -> str:
        payload = json.dumps(
            {"v": cls._VERSION, "o": offset},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def decode(cls, cursor: str) -> int:
        padded_cursor = cursor + ("=" * (-len(cursor) % 4))
        try:
            payload = base64.urlsafe_b64decode(padded_cursor.encode("ascii"))
            decoded = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
            raise InvalidRequestError(details={"cursor": "Malformed cursor."})

        offset = decoded.get("o")
        if (
            decoded.get("v") != cls._VERSION
            or not isinstance(offset, int)
            or offset < 0
        ):
            raise InvalidRequestError(details={"cursor": "Malformed cursor."})

        return offset


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

    def get_many_by_flattened_path(
        self,
        *,
        association_model: ModelType,
        association_source_column: str,
        association_target_column: str,
        source_filter_value: Any,
        association_row_filter: dict[str, Any] | None,
        target_model: ModelType,
        target_identifier_column: str,
        target_join_column: str,
        target_row_filter: dict[str, Any] | None,
    ) -> list[Any]:
        """Return target records for one validated two-hop flattened link path."""
        association_source = self._get_column(association_model, association_source_column)
        association_target = self._get_column(association_model, association_target_column)
        target_join = self._get_column(target_model, target_join_column)
        target_identifier = self._get_column(target_model, target_identifier_column)

        statement = (
            select(target_model)
            .select_from(association_model)
            .join(target_model, target_join == association_target)
            .where(association_source == source_filter_value)
            .distinct()
            .order_by(target_identifier)
        )
        for column_name, value in (association_row_filter or {}).items():
            statement = statement.where(
                self._get_column(association_model, column_name) == value
            )
        for column_name, value in (target_row_filter or {}).items():
            statement = statement.where(self._get_column(target_model, column_name) == value)
        return list(self._session.execute(statement).scalars().all())

    def search(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        mapping: ResolvedObjectMapping,
        query: str | None,
        searchable_property_columns: Sequence[str],
        filters: Sequence[RepositorySearchFilter],
        sort: Sequence[RepositorySearchSort],
        limit: int,
        cursor: str | None,
    ) -> SearchResultPage:
        """Search one object type using trusted validated metadata only."""
        offset = 0 if cursor is None else ObjectSearchCursorCodec.decode(cursor)
        normalized_sort = self._normalize_sort(sort, mapping)

        statement = select(mapping.model)
        for column_name, value in (definition.source.rowFilter or {}).items():
            statement = statement.where(self._get_column(mapping.model, column_name) == value)

        if query is not None:
            escaped_query = self._escape_like(query.lower())
            query_predicates = [
                func.lower(sa_cast(self._get_column(mapping.model, column_name), String)).like(
                    f"%{escaped_query}%",
                    escape="\\",
                )
                for column_name in searchable_property_columns
            ]
            statement = statement.where(or_(*query_predicates))

        for filter_definition in filters:
            statement = statement.where(
                self._build_filter_expression(mapping.model, filter_definition)
            )

        for sort_definition in normalized_sort:
            column = self._get_column(mapping.model, sort_definition.column_name)
            order_clause = column.asc() if sort_definition.direction == "asc" else column.desc()
            statement = statement.order_by(order_clause.nullslast())

        statement = statement.offset(offset).limit(limit + 1)
        records = list(self._session.execute(statement).scalars().all())
        has_more = len(records) > limit
        page_records = records[:limit]
        next_cursor = (
            ObjectSearchCursorCodec.encode(offset + limit) if has_more else None
        )

        return SearchResultPage(
            records=page_records,
            next_cursor=next_cursor,
            has_more=has_more,
        )

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

    def _normalize_sort(
        self,
        sort: Sequence[RepositorySearchSort],
        mapping: ResolvedObjectMapping,
    ) -> tuple[RepositorySearchSort, ...]:
        normalized = list(sort)
        if (
            not normalized
            or normalized[-1].property_key != mapping.identifier_property_key
        ):
            normalized.append(
                RepositorySearchSort(
                    property_key=mapping.identifier_property_key,
                    column_name=mapping.identifier_column,
                    direction="asc",
                )
            )
        return tuple(normalized)

    def _build_filter_expression(
        self,
        model: ModelType,
        filter_definition: RepositorySearchFilter,
    ) -> Any:
        column = self._get_column(model, filter_definition.column_name)
        operator = filter_definition.operator
        value = filter_definition.value

        if operator == "equals":
            return column == value
        if operator == "notEquals":
            return column != value
        if operator == "in":
            return column.in_(value)
        if operator == "contains":
            escaped_value = self._escape_like(str(value).lower())
            return func.lower(sa_cast(column, String)).like(
                f"%{escaped_value}%",
                escape="\\",
            )
        if operator == "greaterThan":
            return column > value
        if operator == "greaterThanOrEqual":
            return column >= value
        if operator == "lessThan":
            return column < value
        if operator == "lessThanOrEqual":
            return column <= value
        raise ValueError(f"Unsupported operator '{operator}'.")

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
