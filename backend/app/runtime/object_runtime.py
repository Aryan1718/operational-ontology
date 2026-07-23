"""Runtime service for ontology object retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.exceptions import InvalidRequestError, ObjectNotFoundError, ObjectTypeNotFoundError
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import (
    ObjectRepository,
    RepositorySearchFilter,
    RepositorySearchSort,
    ResolvedObjectMapping,
    SearchResultPage,
)
from app.schemas.objects import ObjectSearchRequest, ObjectSearchResponse, OntologyObjectResponse
from app.schemas.ontology import OntologyObjectTypeDefinition, OntologyPropertyDefinition

_OPERATOR_TYPES: dict[str, set[str]] = {
    "string": {"equals", "notEquals", "in", "contains"},
    "enum": {"equals", "notEquals", "in"},
    "integer": {
        "equals",
        "notEquals",
        "in",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    },
    "number": {
        "equals",
        "notEquals",
        "in",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    },
    "currency": {
        "equals",
        "notEquals",
        "in",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    },
    "date": {
        "equals",
        "notEquals",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    },
    "datetime": {
        "equals",
        "notEquals",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    },
    "boolean": {"equals", "notEquals"},
}


@dataclass(frozen=True, slots=True)
class LoadedOntologyObject:
    """Resolved object metadata and backing ORM record."""

    definition: OntologyObjectTypeDefinition
    mapping: ResolvedObjectMapping
    record: Any


@dataclass(frozen=True, slots=True)
class ObjectSearchResult:
    """Normalized object search payload plus pagination metadata."""

    response: ObjectSearchResponse
    next_cursor: str | None
    has_more: bool


class ObjectRuntime:
    """Resolve one ontology object from trusted metadata and operational data."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        repository: ObjectRepository,
    ) -> None:
        self._registry = registry
        self._repository = repository

    def get_object(self, object_type: str, object_id: str) -> OntologyObjectResponse:
        """Return one mapped ontology object or raise a structured application error."""
        return self.map_loaded_object(self.load_object(object_type, object_id))

    def search_objects(
        self,
        object_type: str,
        request: ObjectSearchRequest,
    ) -> ObjectSearchResult:
        """Search one ontology object type using validated ontology metadata."""
        definition = self._registry.get_object_type(object_type)
        if definition is None:
            raise ObjectTypeNotFoundError(object_type)

        mapping = self._repository.resolve_object_mapping(definition)
        searchable_columns = self._resolve_searchable_columns(definition, request.query)
        filters = tuple(
            self._validate_filter(definition, filter_definition)
            for filter_definition in request.filters or []
        )
        sort = tuple(
            self._validate_sort(definition, sort_definition)
            for sort_definition in request.sort or []
        )

        page = self._repository.search(
            definition=definition,
            mapping=mapping,
            query=request.query,
            searchable_property_columns=searchable_columns,
            filters=filters,
            sort=sort,
            limit=request.limit,
            cursor=request.cursor,
        )

        return self._map_search_result(definition, mapping, page)

    def load_object(self, object_type: str, object_id: str) -> LoadedOntologyObject:
        """Load one object definition, mapping, and ORM record."""
        definition = self._registry.get_object_type(object_type)
        if definition is None:
            raise ObjectTypeNotFoundError(object_type)

        mapping = self._repository.resolve_object_mapping(definition)
        record = self._repository.get_one(
            model=mapping.model,
            identifier_column=mapping.identifier_column,
            object_id=object_id,
            row_filter=definition.source.rowFilter,
        )

        if record is None:
            raise ObjectNotFoundError(object_type, object_id)

        return LoadedOntologyObject(
            definition=definition,
            mapping=mapping,
            record=record,
        )

    def map_loaded_object(self, loaded: LoadedOntologyObject) -> OntologyObjectResponse:
        """Map one previously loaded object into the public API schema."""
        return self.map_record(
            definition=loaded.definition,
            mapping=loaded.mapping,
            record=loaded.record,
        )

    def map_record(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        mapping: ResolvedObjectMapping,
        record: Any,
    ) -> OntologyObjectResponse:
        """Map one trusted ORM record into the public ontology object schema."""
        properties = {
            property_key: self._read_record_value(
                record=record,
                model=mapping.model,
                property_definition=property_definition,
            )
            for property_key, property_definition in definition.storedProperties.items()
        }
        display_name = properties.get(mapping.title_property_key)
        response_object_id = properties[mapping.identifier_property_key]

        return OntologyObjectResponse(
            objectType=definition.key,
            objectId=str(response_object_id),
            displayName=None if display_name is None else str(display_name),
            properties=properties,
        )

    def _map_search_result(
        self,
        definition: OntologyObjectTypeDefinition,
        mapping: ResolvedObjectMapping,
        page: SearchResultPage,
    ) -> ObjectSearchResult:
        return ObjectSearchResult(
            response=ObjectSearchResponse(
                objectType=definition.key,
                objects=[
                    self.map_record(definition=definition, mapping=mapping, record=record)
                    for record in page.records
                ],
            ),
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    def _resolve_searchable_columns(
        self,
        definition: OntologyObjectTypeDefinition,
        query: str | None,
    ) -> tuple[str, ...]:
        if query is None:
            return ()

        columns = tuple(
            property_definition.sourceColumn
            for property_definition in definition.storedProperties.values()
            if property_definition.searchable
        )
        if not columns:
            raise InvalidRequestError(
                details={
                    "objectType": definition.key,
                    "reason": "Object type has no searchable properties.",
                }
            )
        return columns

    def _validate_filter(
        self,
        definition: OntologyObjectTypeDefinition,
        filter_definition: Any,
    ) -> RepositorySearchFilter:
        property_definition = self._get_queryable_property_definition(
            definition=definition,
            property_key=filter_definition.property,
        )
        if not property_definition.filterable:
            raise InvalidRequestError(
                details={
                    "objectType": definition.key,
                    "property": filter_definition.property,
                    "reason": "Property is not filterable.",
                }
            )

        self._validate_operator(
            property_key=filter_definition.property,
            property_definition=property_definition,
            operator=filter_definition.operator,
        )
        value = self._coerce_filter_value(
            property_key=filter_definition.property,
            property_definition=property_definition,
            operator=filter_definition.operator,
            raw_value=filter_definition.value,
        )
        return RepositorySearchFilter(
            property_key=filter_definition.property,
            column_name=property_definition.sourceColumn,
            operator=filter_definition.operator,
            value=value,
        )

    def _validate_sort(
        self,
        definition: OntologyObjectTypeDefinition,
        sort_definition: Any,
    ) -> RepositorySearchSort:
        property_definition = self._get_queryable_property_definition(
            definition=definition,
            property_key=sort_definition.property,
        )
        if not property_definition.sortable:
            raise InvalidRequestError(
                details={
                    "objectType": definition.key,
                    "property": sort_definition.property,
                    "reason": "Property is not sortable.",
                }
            )

        return RepositorySearchSort(
            property_key=sort_definition.property,
            column_name=property_definition.sourceColumn,
            direction=sort_definition.direction,
        )

    def _get_queryable_property_definition(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        property_key: str,
    ) -> OntologyPropertyDefinition:
        property_definition = definition.storedProperties.get(property_key)
        if property_definition is not None:
            return property_definition

        derived_properties = getattr(definition, "derivedProperties", {}) or {}
        if property_key in derived_properties:
            raise InvalidRequestError(
                details={
                    "objectType": definition.key,
                    "property": property_key,
                    "reason": "Derived properties are not queryable.",
                }
            )

        raise InvalidRequestError(
            details={
                "objectType": definition.key,
                "property": property_key,
                "reason": "Unknown property.",
            }
        )

    def _validate_operator(
        self,
        *,
        property_key: str,
        property_definition: OntologyPropertyDefinition,
        operator: str,
    ) -> None:
        allowed_operators = _OPERATOR_TYPES.get(property_definition.type, set())
        if operator not in allowed_operators:
            raise InvalidRequestError(
                details={
                    "property": property_key,
                    "operator": operator,
                    "reason": "Unsupported operator for property type.",
                }
            )

    def _coerce_filter_value(
        self,
        *,
        property_key: str,
        property_definition: OntologyPropertyDefinition,
        operator: str,
        raw_value: Any,
    ) -> Any:
        if operator == "in":
            if not isinstance(raw_value, list):
                raise InvalidRequestError(
                    details={
                        "property": property_key,
                        "reason": "Filter value must be a list for 'in'.",
                    }
                )
            return [
                self._coerce_scalar_value(property_key, property_definition, item)
                for item in raw_value
            ]

        return self._coerce_scalar_value(property_key, property_definition, raw_value)

    def _coerce_scalar_value(
        self,
        property_key: str,
        property_definition: OntologyPropertyDefinition,
        raw_value: Any,
    ) -> Any:
        property_type = property_definition.type

        if property_type == "string":
            if not isinstance(raw_value, str):
                raise self._invalid_filter_value_error(property_key)
            return raw_value

        if property_type == "enum":
            if not isinstance(raw_value, str):
                raise self._invalid_filter_value_error(property_key)
            enum_values = self._registry.enums_by_key.get(property_definition.enum or "", ())
            if raw_value not in enum_values:
                raise InvalidRequestError(
                    details={
                        "property": property_key,
                        "value": raw_value,
                        "reason": "Invalid enum value.",
                    }
                )
            return raw_value

        if property_type == "integer":
            if not isinstance(raw_value, int) or isinstance(raw_value, bool):
                raise self._invalid_filter_value_error(property_key)
            return raw_value

        if property_type in {"number", "currency"}:
            if not isinstance(raw_value, (int, float, Decimal)) or isinstance(raw_value, bool):
                raise self._invalid_filter_value_error(property_key)
            return Decimal(str(raw_value))

        if property_type == "boolean":
            if not isinstance(raw_value, bool):
                raise self._invalid_filter_value_error(property_key)
            return raw_value

        if property_type == "date":
            if isinstance(raw_value, date) and not isinstance(raw_value, datetime):
                return raw_value
            if isinstance(raw_value, str):
                try:
                    return date.fromisoformat(raw_value)
                except ValueError as exc:
                    raise self._invalid_filter_value_error(property_key) from exc
            raise self._invalid_filter_value_error(property_key)

        if property_type == "datetime":
            if isinstance(raw_value, datetime):
                return raw_value
            if isinstance(raw_value, str):
                try:
                    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise self._invalid_filter_value_error(property_key) from exc
            raise self._invalid_filter_value_error(property_key)

        raise InvalidRequestError(
            details={
                "property": property_key,
                "reason": "Unsupported property type.",
            }
        )

    def _invalid_filter_value_error(self, property_key: str) -> InvalidRequestError:
        return InvalidRequestError(
            details={
                "property": property_key,
                "reason": "Invalid filter value type.",
            }
        )

    def _read_record_value(
        self,
        *,
        record: Any,
        model: type[Any],
        property_definition: OntologyPropertyDefinition,
    ) -> Any:
        attribute_name = self._repository.get_column_attribute_name(
            model,
            property_definition.sourceColumn,
        )
        return getattr(record, attribute_name)
