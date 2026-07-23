"""Object repository mapping validation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidOntologyMappingError, InvalidRequestError
from app.models.mitigation import MitigationPlanStep
from app.models.supply_chain import Supplier
from app.ontology.loader import load_ontology_registry
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import (
    ObjectRepository,
    RepositorySearchFilter,
    RepositorySearchSort,
)


@pytest.fixture
def registry() -> OntologyRegistry:
    return load_ontology_registry()


@pytest.fixture
def repository() -> ObjectRepository:
    return ObjectRepository(Session())


def test_repository_resolves_supplier_to_expected_model_and_identifier(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    supplier_definition = registry.get_object_type("Supplier")
    assert supplier_definition is not None

    mapping = repository.resolve_object_mapping(supplier_definition)

    assert supplier_definition.source.primaryKeyColumn == "id"
    assert mapping.model is Supplier
    assert mapping.model.__tablename__ == "suppliers"
    assert mapping.identifier_property_key == "supplierCode"
    assert mapping.identifier_column == "supplier_code"
    assert mapping.title_property_key == "name"


def test_repository_rejects_non_primary_source_key_column(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    supplier_definition = registry.get_object_type("Supplier")
    assert supplier_definition is not None
    invalid_definition = supplier_definition.model_copy(
        update={
            "source": supplier_definition.source.model_copy(
                update={"primaryKeyColumn": "supplier_code"}
            )
        }
    )

    with pytest.raises(InvalidOntologyMappingError) as exc_info:
        repository.resolve_object_mapping(invalid_definition)

    assert exc_info.value.code == "INVALID_ONTOLOGY_MAPPING"
    assert exc_info.value.details["objectType"] == "Supplier"
    assert "source primary key column" in str(exc_info.value.details["reason"])


def test_repository_rejects_missing_identifier_property_metadata(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    supplier_definition = registry.get_object_type("Supplier")
    assert supplier_definition is not None
    invalid_definition = supplier_definition.model_copy(
        update={"primaryKeyProperty": "missingCode"}
    )

    with pytest.raises(InvalidOntologyMappingError) as exc_info:
        repository.resolve_object_mapping(invalid_definition)

    assert exc_info.value.code == "INVALID_ONTOLOGY_MAPPING"
    assert exc_info.value.details["objectType"] == "Supplier"
    assert "Missing identifier property" in str(exc_info.value.details["reason"])


def test_repository_rejects_identifier_column_missing_on_model(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    supplier_definition = registry.get_object_type("Supplier")
    assert supplier_definition is not None
    invalid_definition = supplier_definition.model_copy(
        update={
            "storedProperties": {
                **supplier_definition.storedProperties,
                "supplierCode": supplier_definition.storedProperties[
                    "supplierCode"
                ].model_copy(update={"sourceColumn": "supplier_code_missing"}),
            }
        }
    )

    with pytest.raises(InvalidOntologyMappingError) as exc_info:
        repository.resolve_object_mapping(invalid_definition)

    assert exc_info.value.code == "INVALID_ONTOLOGY_MAPPING"
    assert exc_info.value.details["objectType"] == "Supplier"
    assert "identifier column" in str(exc_info.value.details["reason"])


def test_repository_rejects_mismatched_object_type_table_mapping(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    supplier_definition = registry.get_object_type("Supplier")
    assert supplier_definition is not None
    invalid_definition = supplier_definition.model_copy(
        update={
            "source": supplier_definition.source.model_copy(update={"table": "parts"})
        }
    )

    with pytest.raises(InvalidOntologyMappingError) as exc_info:
        repository.resolve_object_mapping(invalid_definition)

    assert exc_info.value.code == "INVALID_ONTOLOGY_MAPPING"
    assert exc_info.value.details["objectType"] == "Supplier"
    assert "expected SQLAlchemy model table" in str(exc_info.value.details["reason"])


def test_repository_rejects_inventory_transfer_step_alias_mapping(
    repository: ObjectRepository,
    registry: OntologyRegistry,
) -> None:
    inventory_transfer_definition = registry.get_object_type("InventoryTransfer")
    assert inventory_transfer_definition is not None
    assert (
        inventory_transfer_definition.source.table == MitigationPlanStep.__tablename__
    )

    with pytest.raises(InvalidOntologyMappingError) as exc_info:
        repository.resolve_object_mapping(inventory_transfer_definition)

    assert exc_info.value.code == "INVALID_ONTOLOGY_MAPPING"
    assert exc_info.value.details["objectType"] == "InventoryTransfer"
    assert "Unsupported object type" in str(exc_info.value.details["reason"])


def test_repository_search_filters_supplier_equality(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    page = repository.search(
        definition=definition,
        mapping=mapping,
        query=None,
        searchable_property_columns=(),
        filters=(
            RepositorySearchFilter(
                property_key="status",
                column_name="status",
                operator="equals",
                value="delayed",
            ),
        ),
        sort=(
            RepositorySearchSort(
                property_key="supplierCode",
                column_name="supplier_code",
                direction="asc",
            ),
        ),
        limit=20,
        cursor=None,
    )

    assert [record.supplier_code for record in page.records] == ["S-103"]
    assert page.has_more is False
    assert page.next_cursor is None


def test_repository_search_matches_text_across_searchable_properties(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    page = repository.search(
        definition=definition,
        mapping=mapping,
        query="vertex",
        searchable_property_columns=("supplier_code", "name", "country", "region", "status"),
        filters=(),
        sort=(
            RepositorySearchSort(
                property_key="supplierCode",
                column_name="supplier_code",
                direction="asc",
            ),
        ),
        limit=20,
        cursor=None,
    )

    assert [record.supplier_code for record in page.records] == ["S-102"]


def test_repository_search_applies_numeric_comparison(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    page = repository.search(
        definition=definition,
        mapping=mapping,
        query=None,
        searchable_property_columns=(),
        filters=(
            RepositorySearchFilter(
                property_key="reliabilityScore",
                column_name="reliability_score",
                operator="greaterThanOrEqual",
                value=Decimal("90"),
            ),
        ),
        sort=(
            RepositorySearchSort(
                property_key="reliabilityScore",
                column_name="reliability_score",
                direction="asc",
            ),
        ),
        limit=20,
        cursor=None,
    )

    assert [record.supplier_code for record in page.records] == ["S-103", "S-101"]


def test_repository_search_applies_sorting_and_identifier_tie_breaking(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    database_session.add_all(
        [
            Supplier(
                id=uuid4(),
                supplier_code="S-104",
                name="Atlas Circuits",
                country="United States",
                region="West",
                status="active",
                reliability_score=Decimal("88.00"),
                default_lead_time_days=4,
                created_at=datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
            ),
            Supplier(
                id=uuid4(),
                supplier_code="S-105",
                name="Beacon Components",
                country="United States",
                region="West",
                status="active",
                reliability_score=Decimal("88.00"),
                default_lead_time_days=4,
                created_at=datetime(2026, 7, 15, 8, 5, tzinfo=timezone.utc),
                updated_at=datetime(2026, 7, 15, 8, 5, tzinfo=timezone.utc),
            ),
        ]
    )
    database_session.commit()

    page = repository.search(
        definition=definition,
        mapping=mapping,
        query=None,
        searchable_property_columns=(),
        filters=(),
        sort=(
            RepositorySearchSort(
                property_key="reliabilityScore",
                column_name="reliability_score",
                direction="asc",
            ),
        ),
        limit=20,
        cursor=None,
    )

    supplier_codes = [record.supplier_code for record in page.records]
    assert supplier_codes.index("S-104") < supplier_codes.index("S-105")


def test_repository_search_paginates_with_opaque_cursor(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)
    sort = (
        RepositorySearchSort(
            property_key="supplierCode",
            column_name="supplier_code",
            direction="asc",
        ),
    )

    first_page = repository.search(
        definition=definition,
        mapping=mapping,
        query=None,
        searchable_property_columns=(),
        filters=(),
        sort=sort,
        limit=1,
        cursor=None,
    )

    assert [record.supplier_code for record in first_page.records] == ["S-101"]
    assert first_page.has_more is True
    assert first_page.next_cursor is not None

    second_page = repository.search(
        definition=definition,
        mapping=mapping,
        query=None,
        searchable_property_columns=(),
        filters=(),
        sort=sort,
        limit=1,
        cursor=first_page.next_cursor,
    )

    assert [record.supplier_code for record in second_page.records] == ["S-102"]
    assert second_page.has_more is True
    assert second_page.next_cursor is not None


def test_repository_search_rejects_malformed_cursor(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    with pytest.raises(InvalidRequestError) as exc_info:
        repository.search(
            definition=definition,
            mapping=mapping,
            query=None,
            searchable_property_columns=(),
            filters=(),
            sort=(),
            limit=20,
            cursor="not-a-valid-cursor",
        )

    assert exc_info.value.details["cursor"] == "Malformed cursor."


def test_repository_search_does_not_allow_arbitrary_column_access(
    database_session: Session,
    registry: OntologyRegistry,
) -> None:
    repository = ObjectRepository(database_session)
    definition = registry.get_object_type("Supplier")
    assert definition is not None
    mapping = repository.resolve_object_mapping(definition)

    with pytest.raises(KeyError):
        repository.search(
            definition=definition,
            mapping=mapping,
            query=None,
            searchable_property_columns=(),
            filters=(
                RepositorySearchFilter(
                    property_key="status",
                    column_name="status; drop table suppliers",
                    operator="equals",
                    value="active",
                ),
            ),
            sort=(),
            limit=20,
            cursor=None,
        )
