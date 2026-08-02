"""Runtime service for stored and flattened ontology link traversal."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import (
    InvalidOntologyMappingError,
    LinkNotFoundError,
    LinkResolutionNotImplementedError,
)
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
)
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository
from app.runtime.authorization_service import AuthorizationService
from app.runtime.object_runtime import LoadedOntologyObject, ObjectRuntime
from app.schemas.objects import (
    AggregateLinkObjectsResponse,
    AggregateLinkedObjectsResponse,
    LinkedObjectsResponse,
    OntologyObjectReference,
    OntologyObjectResponse,
)
from app.schemas.ontology import (
    OntologyLinkTypeDefinition,
    OntologyObjectTypeDefinition,
    OntologyPropertyDefinition,
)

_SINGLE_TARGET_CARDINALITIES = {"many-to-one", "one-to-one"}


class LinkRuntime:
    """Resolve ontology links backed by trusted declared metadata."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        repository: ObjectRepository,
        object_runtime: ObjectRuntime,
        authorization_service: AuthorizationService,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._object_runtime = object_runtime
        self._authorization_service = authorization_service

    def get_linked_objects(
        self,
        object_type: str,
        object_id: str,
        link_type: str,
        actor: ActorContext,
    ) -> LinkedObjectsResponse:
        """Return linked objects for one declared ontology link."""
        source_object = self._object_runtime.load_object(object_type, object_id)
        source_response = self._object_runtime.map_loaded_object(source_object)
        link_definition = self._get_declared_link_definition(
            source_definition=source_object.definition,
            link_type=link_type,
        )
        target_decision = self._authorize_link_traversal(
            actor=actor,
            source_definition=source_object.definition,
            link_definition=link_definition,
        )
        return self._resolve_link_from_source(
            source_object=source_object,
            source_response=source_response,
            link_definition=link_definition,
            target_projection_key=(
                None
                if target_decision.obligations is None
                else target_decision.obligations.projection_key
            ),
        )

    def get_all_links(
        self,
        object_type: str,
        object_id: str,
        actor: ActorContext,
    ) -> AggregateLinkedObjectsResponse:
        """Return all declared links for one source object."""
        source_object = self._object_runtime.load_object(object_type, object_id)
        source_response = self._object_runtime.map_loaded_object(source_object)

        links: list[AggregateLinkObjectsResponse] = []
        for link_key in source_object.definition.links:
            link_definition = self._get_declared_link_definition(
                source_definition=source_object.definition,
                link_type=link_key,
            )
            target_decision = self._authorize_link_traversal(
                actor=actor,
                source_definition=source_object.definition,
                link_definition=link_definition,
            )
            if link_definition.kind not in {"stored", "flattened"}:
                links.append(
                    AggregateLinkObjectsResponse(
                        linkType=link_definition.key,
                        targetObjectType=link_definition.targetObjectType,
                        cardinality=link_definition.cardinality,
                        resolutionStatus="notImplemented",
                        objects=[],
                    )
                )
                continue

            resolved_link = self._resolve_link_from_source(
                source_object=source_object,
                source_response=source_response,
                link_definition=link_definition,
                target_projection_key=(
                    None
                    if target_decision.obligations is None
                    else target_decision.obligations.projection_key
                ),
            )
            links.append(
                AggregateLinkObjectsResponse(
                    linkType=resolved_link.linkType,
                    targetObjectType=resolved_link.targetObjectType,
                    cardinality=resolved_link.cardinality,
                    resolutionStatus="resolved",
                    objects=resolved_link.objects,
                )
            )

        return AggregateLinkedObjectsResponse(
            source=OntologyObjectReference(
                objectType=source_response.objectType,
                objectId=source_response.objectId,
            ),
            links=links,
        )

    def _resolve_link_from_source(
        self,
        *,
        source_object: LoadedOntologyObject,
        source_response: OntologyObjectResponse,
        link_definition: OntologyLinkTypeDefinition,
        target_projection_key: str | None,
    ) -> LinkedObjectsResponse:
        if link_definition.kind == "stored":
            return self._resolve_stored_link_from_source(
                source_object=source_object,
                source_response=source_response,
                link_definition=link_definition,
                target_projection_key=target_projection_key,
            )
        if link_definition.kind == "flattened":
            return self._resolve_flattened_link_from_source(
                source_object=source_object,
                source_response=source_response,
                link_definition=link_definition,
                target_projection_key=target_projection_key,
            )
        raise LinkResolutionNotImplementedError(link_definition.key, link_definition.kind)

    def _get_declared_link_definition(
        self,
        *,
        source_definition: OntologyObjectTypeDefinition,
        link_type: str,
    ) -> OntologyLinkTypeDefinition:
        link_definition = self._registry.get_link_type(link_type)
        if link_definition is None:
            raise LinkNotFoundError(source_definition.key, link_type)
        if link_definition.key not in source_definition.links:
            raise LinkNotFoundError(source_definition.key, link_type)
        if link_definition.sourceObjectType != source_definition.key:
            raise LinkNotFoundError(source_definition.key, link_type)
        return link_definition

    def _authorize_link_traversal(
        self,
        *,
        actor: ActorContext,
        source_definition: OntologyObjectTypeDefinition,
        link_definition: OntologyLinkTypeDefinition,
    ) -> AuthorizationDecision:
        self._authorize_object_read(actor=actor, object_type=source_definition.key)
        self._authorization_service.authorize_or_raise(
            AuthorizationRequest(
                actor=actor,
                capability=AuthorizationCapability.LINK_TRAVERSE,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.LINK_TYPE,
                    resource_key=link_definition.key,
                ),
            )
        )
        return self._authorize_object_read(
            actor=actor,
            object_type=link_definition.targetObjectType,
        )

    def _authorize_object_read(
        self,
        *,
        actor: ActorContext,
        object_type: str,
    ) -> AuthorizationDecision:
        return self._authorization_service.authorize_or_raise(
            AuthorizationRequest(
                actor=actor,
                capability=AuthorizationCapability.OBJECT_READ,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.OBJECT_TYPE,
                    resource_key=object_type,
                ),
            )
        )

    def _resolve_stored_link_from_source(
        self,
        *,
        source_object: LoadedOntologyObject,
        source_response: OntologyObjectResponse,
        link_definition: OntologyLinkTypeDefinition,
        target_projection_key: str | None,
    ) -> LinkedObjectsResponse:
        target_definition = self._require_target_definition(
            source_definition=source_object.definition,
            link_definition=link_definition,
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
            source_definition=source_object.definition,
            source_model=source_object.mapping.model,
            source_property=source_property,
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
        target_records: list[Any] = []
        if source_value is not None:
            target_records = self._repository.get_many_by_column(
                model=target_mapping.model,
                filter_column=target_property.sourceColumn,
                filter_value=source_value,
                row_filter=self._merge_row_filters(
                    target_definition.key,
                    link_definition.storage.rowFilter if link_definition.storage else None,
                    target_definition.source.rowFilter,
                ),
                order_by_column=target_mapping.identifier_column,
            )

        linked_objects = self._map_linked_objects(
            target_definition=target_definition,
            target_mapping=target_mapping,
            target_records=target_records,
            target_projection_key=target_projection_key,
        )
        return self._build_link_response(
            source_response=source_response,
            link_definition=link_definition,
            target_definition=target_definition,
            linked_objects=linked_objects,
        )

    def _resolve_flattened_link_from_source(
        self,
        *,
        source_object: LoadedOntologyObject,
        source_response: OntologyObjectResponse,
        link_definition: OntologyLinkTypeDefinition,
        target_projection_key: str | None,
    ) -> LinkedObjectsResponse:
        source_link, target_link = self._resolve_flattened_path(
            source_definition=source_object.definition,
            link_definition=link_definition,
        )
        association_definition = self._require_target_definition(
            source_definition=source_object.definition,
            link_definition=source_link,
        )
        target_definition = self._require_target_definition(
            source_definition=association_definition,
            link_definition=target_link,
        )
        association_mapping = self._repository.resolve_object_mapping(association_definition)
        target_mapping = self._repository.resolve_object_mapping(target_definition)

        source_property = self._require_stored_property(
            definition=source_object.definition,
            property_key=source_link.sourceJoinProperty,
            field_name="flattened source join property",
            link_definition=link_definition,
        )
        association_source_property = self._require_stored_property(
            definition=association_definition,
            property_key=source_link.targetJoinProperty,
            field_name="flattened association source join property",
            link_definition=link_definition,
        )
        association_target_property = self._require_stored_property(
            definition=association_definition,
            property_key=target_link.sourceJoinProperty,
            field_name="flattened association target join property",
            link_definition=link_definition,
        )
        target_property = self._require_stored_property(
            definition=target_definition,
            property_key=target_link.targetJoinProperty,
            field_name="flattened target join property",
            link_definition=link_definition,
        )

        self._validate_stored_link_storage(
            link_definition=source_link,
            source_definition=source_object.definition,
            source_model=source_object.mapping.model,
            source_property=source_property,
            target_definition=association_definition,
            target_model=association_mapping.model,
            target_property=association_source_property,
        )
        self._validate_stored_link_storage(
            link_definition=target_link,
            source_definition=association_definition,
            source_model=association_mapping.model,
            source_property=association_target_property,
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
        target_records: list[Any] = []
        if source_value is not None:
            target_records = self._repository.get_many_by_flattened_path(
                association_model=association_mapping.model,
                association_source_column=association_source_property.sourceColumn,
                association_target_column=association_target_property.sourceColumn,
                source_filter_value=source_value,
                association_row_filter=self._merge_row_filters(
                    association_definition.key,
                    association_definition.source.rowFilter,
                    source_link.storage.rowFilter if source_link.storage else None,
                    target_link.storage.rowFilter if target_link.storage else None,
                ),
                target_model=target_mapping.model,
                target_identifier_column=target_mapping.identifier_column,
                target_join_column=target_property.sourceColumn,
                target_row_filter=target_definition.source.rowFilter,
            )

        linked_objects = self._map_linked_objects(
            target_definition=target_definition,
            target_mapping=target_mapping,
            target_records=target_records,
            target_projection_key=target_projection_key,
        )
        return self._build_link_response(
            source_response=source_response,
            link_definition=link_definition,
            target_definition=target_definition,
            linked_objects=linked_objects,
        )

    def _resolve_flattened_path(
        self,
        *,
        source_definition: OntologyObjectTypeDefinition,
        link_definition: OntologyLinkTypeDefinition,
    ) -> tuple[OntologyLinkTypeDefinition, OntologyLinkTypeDefinition]:
        if len(link_definition.path) != 2:
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' must declare a two-link path; "
                    f"received {len(link_definition.path)} path entries."
                ),
            )
        source_link = self._registry.get_link_type(link_definition.path[0])
        target_link = self._registry.get_link_type(link_definition.path[1])
        if source_link is None or target_link is None:
            missing_key = (
                link_definition.path[0] if source_link is None else link_definition.path[1]
            )
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' references unknown path link "
                    f"'{missing_key}'."
                ),
            )
        if source_link.kind != "stored" or target_link.kind != "stored":
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' requires stored path links, "
                    f"but received '{source_link.kind}' and '{target_link.kind}'."
                ),
            )
        if source_link.sourceObjectType != source_definition.key:
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' path must start at "
                    f"'{source_definition.key}'."
                ),
            )
        if source_link.targetObjectType != target_link.sourceObjectType:
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' path is discontinuous between "
                    f"'{source_link.key}' and '{target_link.key}'."
                ),
            )
        if target_link.targetObjectType != link_definition.targetObjectType:
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Flattened link '{link_definition.key}' path ends at "
                    f"'{target_link.targetObjectType}' instead of "
                    f"'{link_definition.targetObjectType}'."
                ),
            )
        return source_link, target_link

    def _require_target_definition(
        self,
        *,
        source_definition: OntologyObjectTypeDefinition,
        link_definition: OntologyLinkTypeDefinition,
    ) -> OntologyObjectTypeDefinition:
        target_definition = self._registry.get_object_type(link_definition.targetObjectType)
        if target_definition is None:
            raise InvalidOntologyMappingError(
                source_definition.key,
                (
                    f"Link '{link_definition.key}' references unknown target object "
                    f"type '{link_definition.targetObjectType}'."
                ),
            )
        return target_definition

    def _map_linked_objects(
        self,
        *,
        target_definition: OntologyObjectTypeDefinition,
        target_mapping: Any,
        target_records: list[Any],
        target_projection_key: str | None,
    ) -> list[OntologyObjectResponse]:
        mapped_by_object_id: dict[str, OntologyObjectResponse] = {}
        for record in target_records:
            mapped = self._object_runtime.map_record(
                definition=target_definition,
                mapping=target_mapping,
                record=record,
            )
            projected = self._apply_projection(mapped, target_projection_key)
            mapped_by_object_id[projected.objectId] = projected
        return [mapped_by_object_id[key] for key in sorted(mapped_by_object_id)]

    def _apply_projection(
        self,
        response: OntologyObjectResponse,
        projection_key: str | None,
    ) -> OntologyObjectResponse:
        _ = projection_key
        return response

    def _build_link_response(
        self,
        *,
        source_response: OntologyObjectResponse,
        link_definition: OntologyLinkTypeDefinition,
        target_definition: OntologyObjectTypeDefinition,
        linked_objects: list[OntologyObjectResponse],
    ) -> LinkedObjectsResponse:
        if (
            link_definition.cardinality in _SINGLE_TARGET_CARDINALITIES
            and len(linked_objects) > 1
        ):
            raise InvalidOntologyMappingError(
                target_definition.key,
                (
                    f"Link '{link_definition.key}' declared cardinality "
                    f"'{link_definition.cardinality}' but resolved multiple target objects."
                ),
            )

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
        source_definition: OntologyObjectTypeDefinition,
        source_model: type[Any],
        source_property: OntologyPropertyDefinition,
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

        if (
            storage.table == target_definition.source.table
            and storage.sourceColumn == target_property.sourceColumn
        ):
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
            return

        if (
            storage.table == source_definition.source.table
            and storage.sourceColumn == source_property.sourceColumn
        ):
            self._require_column(
                object_definition=source_definition,
                model=source_model,
                column_name=storage.sourceColumn,
                field_name="stored link column",
            )
            for row_filter_column in storage.rowFilter or {}:
                self._require_column(
                    object_definition=source_definition,
                    model=source_model,
                    column_name=row_filter_column,
                    field_name="stored link row filter column",
                )
            return

        raise InvalidOntologyMappingError(
            target_definition.key,
            (
                f"Link '{link_definition.key}' storage does not match either the "
                "source join property column or the target join property column."
            ),
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

    def _merge_row_filters(
        self,
        object_type: str,
        *row_filters: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        merged: dict[str, Any] = {}
        for row_filter in row_filters:
            for column_name, value in (row_filter or {}).items():
                if column_name in merged and merged[column_name] != value:
                    raise InvalidOntologyMappingError(
                        object_type,
                        (
                            f"Conflicting row-filter values were declared for column "
                            f"'{column_name}'."
                        ),
                    )
                merged[column_name] = value
        return merged or None
