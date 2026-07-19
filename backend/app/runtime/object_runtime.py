"""Runtime service for ontology object retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import ObjectNotFoundError, ObjectTypeNotFoundError
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository, ResolvedObjectMapping
from app.schemas.objects import OntologyObjectResponse
from app.schemas.ontology import OntologyObjectTypeDefinition, OntologyPropertyDefinition


@dataclass(frozen=True, slots=True)
class LoadedOntologyObject:
    """Resolved object metadata and backing ORM record."""

    definition: OntologyObjectTypeDefinition
    mapping: ResolvedObjectMapping
    record: Any


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
