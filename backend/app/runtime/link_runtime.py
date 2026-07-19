"""Runtime service for stored ontology link traversal."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import (
    InvalidOntologyMappingError,
    LinkNotFoundError,
    LinkResolutionNotImplementedError,
)
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.objects import (
    LinkedObjectsResponse,
    OntologyObjectReference,
    OntologyObjectResponse,
)
from app.schemas.ontology import (
    OntologyLinkTypeDefinition,
    OntologyObjectTypeDefinition,
    OntologyPropertyDefinition,
)


class LinkRuntime:
    """Resolve directly stored ontology links backed by declared property mappings."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        repository: ObjectRepository,
        object_runtime: ObjectRuntime,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._object_runtime = object_runtime

    def get_linked_objects(
        self,
        object_type: str,
        object_id: str,
        link_type: str,
    ) -> LinkedObjectsResponse:
        """Return linked objects for one stored ontology link."""
        source_object = self._object_runtime.load_object(object_type, object_id)
        source_response = self._object_runtime.map_loaded_object(source_object)

        link_definition = self._registry.get_link_type(link_type)
        if link_definition is None:
            raise LinkNotFoundError(object_type, link_type)

        if link_definition.key not in source_object.definition.links:
            raise LinkNotFoundError(object_type, link_type)

        if link_definition.sourceObjectType != source_object.definition.key:
            raise LinkNotFoundError(object_type, link_type)

        if link_definition.kind != "stored":
            raise LinkResolutionNotImplementedError(link_type, link_definition.kind)

        target_definition = self._registry.get_object_type(link_definition.targetObjectType)
        if target_definition is None:
            raise InvalidOntologyMappingError(
                source_object.definition.key,
                (
                    f"Link '{link_definition.key}' references unknown target object "
                    f"type '{link_definition.targetObjectType}'."
                ),
            )

        source_property = self._require_stored_property(
            definition=source_object.definition,
            property_key=link_definition.sourceJoinProperty,
            field_name="source join property",
            link_definition=link_definition,
        )
        target_property = self._require_stored_property(
            definition=target_definition,
            property_key=link_definition.targetJoinProperty,
            field_name="target join property",
            link_definition=link_definition,
        )
        target_mapping = self._repository.resolve_object_mapping(target_definition)

        self._validate_stored_link_storage(
            link_definition=link_definition,
            target_definition=target_definition,
            target_model=target_mapping.model,
            target_property=target_property,
        )

        source_value = self._read_property_value(
            record=source_object.record,
            model=source_object.mapping.model,
            property_definition=source_property,
            object_definition=source_object.definition,
        )
        linked_objects: list[OntologyObjectResponse] = []
        if source_value is not None:
            target_records = self._repository.get_many_by_column(
                model=target_mapping.model,
                filter_column=target_property.sourceColumn,
                filter_value=source_value,
                row_filter=link_definition.storage.rowFilter,
                order_by_column=target_mapping.identifier_column,
            )
            linked_objects = [
                self._object_runtime.map_record(
                    definition=target_definition,
                    mapping=target_mapping,
                    record=record,
                )
                for record in target_records
            ]

        return LinkedObjectsResponse(
            source=OntologyObjectReference(
                objectType=source_response.objectType,
                objectId=source_response.objectId,
            ),
            linkType=link_definition.key,
            targetObjectType=target_definition.key,
            cardinality=link_definition.cardinality,
            objects=linked_objects,
        )

    def _require_stored_property(
        self,
        *,
        definition: OntologyObjectTypeDefinition,
        property_key: str | None,
        field_name: str,
        link_definition: OntologyLinkTypeDefinition,
    ) -> OntologyPropertyDefinition:
        if not property_key:
            raise InvalidOntologyMappingError(
                definition.key,
                f"Link '{link_definition.key}' is missing {field_name} mapping.",
            )
        property_definition = definition.storedProperties.get(property_key)
        if property_definition is None:
            raise InvalidOntologyMappingError(
                definition.key,
                (
                    f"Link '{link_definition.key}' references unknown {field_name} "
                    f"'{property_key}'."
                ),
            )
        return property_definition

    def _validate_stored_link_storage(
        self,
        *,
        link_definition: OntologyLinkTypeDefinition,
        target_definition: OntologyObjectTypeDefinition,
        target_model: type[Any],
        target_property: OntologyPropertyDefinition,
    ) -> None:
        storage = link_definition.storage
        if storage is None:
            raise InvalidOntologyMappingError(
                target_definition.key,
                f"Link '{link_definition.key}' is missing stored link metadata.",
            )
        if storage.table != target_definition.source.table:
            raise InvalidOntologyMappingError(
                target_definition.key,
                (
                    f"Link '{link_definition.key}' storage table does not match "
                    "the target object source table."
                ),
            )
        if storage.sourceColumn != target_property.sourceColumn:
            raise InvalidOntologyMappingError(
                target_definition.key,
                (
                    f"Link '{link_definition.key}' storage column does not match "
                    "the target join property column."
                ),
            )
        self._require_column(
            object_definition=target_definition,
            model=target_model,
            column_name=storage.sourceColumn,
            field_name="stored link column",
        )
        for row_filter_column in storage.rowFilter or {}:
            self._require_column(
                object_definition=target_definition,
                model=target_model,
                column_name=row_filter_column,
                field_name="stored link row filter column",
            )

    def _read_property_value(
        self,
        *,
        record: Any,
        model: type[Any],
        property_definition: OntologyPropertyDefinition,
        object_definition: OntologyObjectTypeDefinition,
    ) -> Any:
        attribute_name = self._require_column(
            object_definition=object_definition,
            model=model,
            column_name=property_definition.sourceColumn,
            field_name="stored property column",
        )
        return getattr(record, attribute_name)

    def _require_column(
        self,
        *,
        object_definition: OntologyObjectTypeDefinition,
        model: type[Any],
        column_name: str,
        field_name: str,
    ) -> str:
        try:
            return self._repository.get_column_attribute_name(model, column_name)
        except KeyError as exc:
            raise InvalidOntologyMappingError(
                object_definition.key,
                f"Unknown {field_name} '{exc.args[0]}'.",
            ) from exc
