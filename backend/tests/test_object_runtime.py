"""Object runtime unit tests for metadata-driven identifier behavior."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.exceptions import InvalidRequestError, ObjectTypeNotFoundError
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import (
    ObjectRepository,
    RepositorySearchFilter,
    RepositorySearchSort,
    ResolvedObjectMapping,
    SearchResultPage,
)
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.objects import ObjectSearchRequest
from app.schemas.ontology import OntologyObjectTypeDefinition


class _StubRegistry:
    def __init__(self, definition: OntologyObjectTypeDefinition) -> None:
        self._definition = definition
        self.enums_by_key = {"statusEnum": ("active", "delayed")}

    def get_object_type(self, object_type: str) -> OntologyObjectTypeDefinition | None:
        if object_type != self._definition.key:
            return None
        return self._definition


class _StubRepository:
    def __init__(
        self,
        *,
        mapping: ResolvedObjectMapping,
        record: object | None,
        search_page: SearchResultPage | None = None,
    ) -> None:
        self._mapping = mapping
        self._record = record
        self._search_page = search_page or SearchResultPage([], None, False)
        self.calls: list[dict[str, object]] = []
        self.search_calls: list[dict[str, object]] = []

    def resolve_object_mapping(
        self,
        definition: OntologyObjectTypeDefinition,
    ) -> ResolvedObjectMapping:
        assert definition.key == self._mapping.object_type
        return self._mapping

    def get_one(
        self,
        *,
        model: type[object],
        identifier_column: str,
        object_id: str,
        row_filter: dict[str, object] | None = None,
    ) -> object | None:
        self.calls.append(
            {
                "model": model,
                "identifierColumn": identifier_column,
                "objectId": object_id,
                "rowFilter": row_filter,
            }
        )
        return self._record

    def search(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        mapping: ResolvedObjectMapping,
        query: str | None,
        searchable_property_columns: tuple[str, ...],
        filters: tuple[RepositorySearchFilter, ...],
        sort: tuple[RepositorySearchSort, ...],
        limit: int,
        cursor: str | None,
    ) -> SearchResultPage:
        self.search_calls.append(
            {
                "definition": definition,
                "mapping": mapping,
                "query": query,
                "searchablePropertyColumns": searchable_property_columns,
                "filters": filters,
                "sort": sort,
                "limit": limit,
                "cursor": cursor,
            }
        )
        return self._search_page

    @staticmethod
    def get_column_attribute_name(model: type[object], column_name: str) -> str:
        del model
        return column_name


class _SyntheticModel:
    pass


def _synthetic_definition() -> OntologyObjectTypeDefinition:
    return OntologyObjectTypeDefinition.model_validate(
        {
            "key": "SyntheticObject",
            "displayName": "Synthetic Object",
            "source": {"table": "synthetic_objects", "primaryKeyColumn": "id"},
            "primaryKeyProperty": "alternateCode",
            "titleProperty": "name",
            "storedProperties": {
                "syntheticId": {
                    "sourceColumn": "id",
                    "type": "string",
                    "required": True,
                    "readOnly": True,
                },
                "preferredCode": {
                    "sourceColumn": "preferred_code",
                    "type": "string",
                    "required": True,
                    "readOnly": True,
                    "searchable": True,
                },
                "alternateCode": {
                    "sourceColumn": "alternate_code",
                    "type": "string",
                    "required": True,
                    "readOnly": True,
                    "searchable": True,
                    "filterable": True,
                    "sortable": True,
                },
                "name": {
                    "sourceColumn": "name",
                    "type": "string",
                    "required": True,
                    "readOnly": True,
                    "searchable": True,
                    "filterable": True,
                    "sortable": True,
                },
                "status": {
                    "sourceColumn": "status",
                    "type": "enum",
                    "enum": "statusEnum",
                    "required": True,
                    "readOnly": True,
                    "searchable": True,
                    "filterable": True,
                    "sortable": True,
                },
                "score": {
                    "sourceColumn": "score",
                    "type": "number",
                    "required": False,
                    "readOnly": True,
                    "filterable": True,
                    "sortable": True,
                },
                "createdAt": {
                    "sourceColumn": "created_at",
                    "type": "datetime",
                    "required": True,
                    "readOnly": True,
                    "filterable": True,
                    "sortable": True,
                },
                "internalNotes": {
                    "sourceColumn": "internal_notes",
                    "type": "string",
                    "required": False,
                    "readOnly": True,
                },
            },
        }
    )


def _build_runtime(search_page: SearchResultPage | None = None) -> tuple[ObjectRuntime, _StubRepository]:
    definition = _synthetic_definition()
    repository = _StubRepository(
        mapping=ResolvedObjectMapping(
            object_type=definition.key,
            model=_SyntheticModel,
            identifier_property_key="alternateCode",
            identifier_column="alternate_code",
            title_property_key="name",
        ),
        record=SimpleNamespace(
            id="internal-1",
            preferred_code="PREF-7",
            alternate_code="ALT-9",
            name="Synthetic Example",
            status="active",
            score=Decimal("72.50"),
            created_at="2026-07-14T08:00:00Z",
            internal_notes="secret",
        ),
        search_page=search_page,
    )
    runtime = ObjectRuntime(
        registry=cast(OntologyRegistry, _StubRegistry(definition)),
        repository=cast(ObjectRepository, repository),
    )
    return runtime, repository


def test_object_runtime_uses_explicit_identifier_metadata_without_guessing() -> None:
    runtime, repository = _build_runtime()

    response = runtime.get_object("SyntheticObject", "ALT-9")

    assert response.objectType == "SyntheticObject"
    assert response.objectId == "ALT-9"
    assert response.displayName == "Synthetic Example"
    assert response.properties == {
        "syntheticId": "internal-1",
        "preferredCode": "PREF-7",
        "alternateCode": "ALT-9",
        "name": "Synthetic Example",
        "status": "active",
        "score": Decimal("72.50"),
        "createdAt": "2026-07-14T08:00:00Z",
        "internalNotes": "secret",
    }
    assert repository.calls == [
        {
            "model": _SyntheticModel,
            "identifierColumn": "alternate_code",
            "objectId": "ALT-9",
            "rowFilter": None,
        }
    ]


def test_search_objects_rejects_unknown_object_type() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(ObjectTypeNotFoundError):
        runtime.search_objects("UnknownType", ObjectSearchRequest.model_validate({}))


def test_search_objects_rejects_unknown_property() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(InvalidRequestError) as exc_info:
        runtime.search_objects(
            "SyntheticObject",
            ObjectSearchRequest.model_validate(
                {"filters": [{"property": "unknown", "operator": "equals", "value": "x"}]}
            ),
        )

    assert exc_info.value.details["property"] == "unknown"
    assert exc_info.value.details["reason"] == "Unknown property."


def test_search_objects_rejects_non_filterable_property() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(InvalidRequestError) as exc_info:
        runtime.search_objects(
            "SyntheticObject",
            ObjectSearchRequest.model_validate(
                {"filters": [{"property": "internalNotes", "operator": "equals", "value": "x"}]}
            ),
        )

    assert exc_info.value.details["property"] == "internalNotes"
    assert exc_info.value.details["reason"] == "Property is not filterable."


def test_search_objects_rejects_non_sortable_property() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(InvalidRequestError) as exc_info:
        runtime.search_objects(
            "SyntheticObject",
            ObjectSearchRequest.model_validate(
                {"sort": [{"property": "internalNotes", "direction": "asc"}]}
            ),
        )

    assert exc_info.value.details["property"] == "internalNotes"
    assert exc_info.value.details["reason"] == "Property is not sortable."


def test_search_objects_rejects_invalid_operator() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(InvalidRequestError) as exc_info:
        runtime.search_objects(
            "SyntheticObject",
            ObjectSearchRequest.model_validate(
                {"filters": [{"property": "score", "operator": "contains", "value": 5}]}
            ),
        )

    assert exc_info.value.details["property"] == "score"
    assert exc_info.value.details["reason"] == "Unsupported operator for property type."


def test_search_objects_rejects_invalid_enum_value() -> None:
    runtime, _ = _build_runtime()

    with pytest.raises(InvalidRequestError) as exc_info:
        runtime.search_objects(
            "SyntheticObject",
            ObjectSearchRequest.model_validate(
                {"filters": [{"property": "status", "operator": "equals", "value": "blocked"}]}
            ),
        )

    assert exc_info.value.details["property"] == "status"
    assert exc_info.value.details["reason"] == "Invalid enum value."


def test_search_objects_invokes_repository_with_validated_metadata() -> None:
    search_page = SearchResultPage(
        records=[
            SimpleNamespace(
                id="internal-1",
                preferred_code="PREF-7",
                alternate_code="ALT-9",
                name="Synthetic Example",
                status="delayed",
                score=Decimal("72.50"),
                created_at="2026-07-14T08:00:00Z",
                internal_notes=None,
            )
        ],
        next_cursor="cursor-1",
        has_more=True,
    )
    runtime, repository = _build_runtime(search_page=search_page)

    response = runtime.search_objects(
        "SyntheticObject",
        ObjectSearchRequest.model_validate(
            {
                "query": " example ",
                "filters": [
                    {"property": "status", "operator": "equals", "value": "delayed"},
                    {"property": "score", "operator": "greaterThan", "value": 70},
                ],
                "sort": [{"property": "score", "direction": "asc"}],
                "limit": 5,
                "cursor": "opaque-cursor",
            }
        ),
    )

    assert len(repository.search_calls) == 1
    call = repository.search_calls[0]
    assert call["query"] == "example"
    assert call["searchablePropertyColumns"] == (
        "preferred_code",
        "alternate_code",
        "name",
        "status",
    )
    filters = cast(tuple[RepositorySearchFilter, ...], call["filters"])
    assert filters[0] == RepositorySearchFilter(
        property_key="status",
        column_name="status",
        operator="equals",
        value="delayed",
    )
    assert filters[1] == RepositorySearchFilter(
        property_key="score",
        column_name="score",
        operator="greaterThan",
        value=Decimal("70"),
    )
    sort = cast(tuple[RepositorySearchSort, ...], call["sort"])
    assert sort == (
        RepositorySearchSort(
            property_key="score",
            column_name="score",
            direction="asc",
        ),
    )
    assert call["limit"] == 5
    assert call["cursor"] == "opaque-cursor"
    assert response.next_cursor == "cursor-1"
    assert response.has_more is True


def test_search_objects_preserves_business_object_identifier_in_results() -> None:
    search_page = SearchResultPage(
        records=[
            SimpleNamespace(
                id="internal-1",
                preferred_code="PREF-7",
                alternate_code="ALT-9",
                name="Synthetic Example",
                status="active",
                score=Decimal("72.50"),
                created_at="2026-07-14T08:00:00Z",
                internal_notes=None,
            )
        ],
        next_cursor=None,
        has_more=False,
    )
    runtime, _ = _build_runtime(search_page=search_page)

    response = runtime.search_objects(
        "SyntheticObject",
        ObjectSearchRequest.model_validate({"sort": [{"property": "name", "direction": "asc"}]}),
    )

    assert response.response.objectType == "SyntheticObject"
    assert response.response.objects[0].objectId == "ALT-9"
    assert response.response.objects[0].properties["alternateCode"] == "ALT-9"
