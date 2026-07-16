"""Immutable ontology registry."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.ontology.actor_context import OntologyRole
from app.ontology.permission_registry import PermissionRegistry
from app.schemas.ontology import (
    OntologyActionTypeDefinition,
    OntologyFunctionDefinition,
    OntologyIdentity,
    OntologyLinkTypeDefinition,
    OntologyObjectTypeDefinition,
    OntologyPermissionsDefinition,
    OntologyRoleDefinition,
)


@dataclass(frozen=True)
class OntologyRegistry:
    """Immutable in-memory registry for loaded ontology metadata."""

    ontology: OntologyIdentity
    object_types_by_key: Mapping[str, OntologyObjectTypeDefinition]
    link_types_by_key: Mapping[str, OntologyLinkTypeDefinition]
    functions_by_key: Mapping[str, OntologyFunctionDefinition]
    action_types_by_key: Mapping[str, OntologyActionTypeDefinition]
    roles_by_key: Mapping[str, OntologyRoleDefinition]
    permission_registry: PermissionRegistry

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "OntologyRegistry":
        """Build an immutable registry from validated ontology metadata."""
        object_types = tuple(
            OntologyObjectTypeDefinition.model_validate(definition)
            for definition in document["objectTypes"].values()
        )
        link_types = tuple(
            OntologyLinkTypeDefinition.model_validate(definition)
            for definition in document["linkTypes"].values()
        )
        functions = tuple(
            OntologyFunctionDefinition.model_validate(definition)
            for definition in document["functions"].values()
        )
        action_types = tuple(
            OntologyActionTypeDefinition.model_validate(definition)
            for definition in document["actions"].values()
        )
        roles = tuple(
            OntologyRoleDefinition.model_validate(definition)
            for definition in document["roles"].values()
        )
        ontology = OntologyIdentity.model_validate(document["ontology"])
        permissions = OntologyPermissionsDefinition.model_validate(document["permissions"])

        object_types_by_key = MappingProxyType(
            {definition.key: definition for definition in object_types}
        )
        link_types_by_key = MappingProxyType(
            {definition.key: definition for definition in link_types}
        )
        functions_by_key = MappingProxyType(
            {
                definition.key or registry_key: definition
                for registry_key, definition in zip(
                    document["functions"].keys(), functions, strict=True
                )
            }
        )
        action_types_by_key = MappingProxyType(
            {
                definition.key or registry_key: definition
                for registry_key, definition in zip(
                    document["actions"].keys(), action_types, strict=True
                )
            }
        )
        roles_by_key = MappingProxyType(
            {
                cls._stringify_role_key(definition.key) or registry_key: definition
                for registry_key, definition in zip(
                    document["roles"].keys(), roles, strict=True
                )
            }
        )
        permission_registry = PermissionRegistry.from_ontology(
            ontology=ontology,
            object_types_by_key=object_types_by_key,
            link_types_by_key=link_types_by_key,
            functions_by_key=functions_by_key,
            action_types_by_key=action_types_by_key,
            roles_by_key=roles_by_key,
            permissions=permissions,
        )

        return cls(
            ontology=ontology,
            object_types_by_key=object_types_by_key,
            link_types_by_key=link_types_by_key,
            functions_by_key=functions_by_key,
            action_types_by_key=action_types_by_key,
            roles_by_key=roles_by_key,
            permission_registry=permission_registry,
        )

    @staticmethod
    def _stringify_role_key(role: OntologyRole | None) -> str | None:
        if role is None:
            return None
        return role.value

    @property
    def object_types(self) -> tuple[OntologyObjectTypeDefinition, ...]:
        """Return object types in deterministic registry order."""
        return tuple(self.object_types_by_key.values())

    @property
    def link_types(self) -> tuple[OntologyLinkTypeDefinition, ...]:
        """Return link types in deterministic registry order."""
        return tuple(self.link_types_by_key.values())

    @property
    def functions(self) -> tuple[OntologyFunctionDefinition, ...]:
        """Return functions in deterministic registry order."""
        return tuple(self.functions_by_key.values())

    @property
    def action_types(self) -> tuple[OntologyActionTypeDefinition, ...]:
        """Return action types in deterministic registry order."""
        return tuple(self.action_types_by_key.values())

    @property
    def roles(self) -> tuple[OntologyRoleDefinition, ...]:
        """Return roles in deterministic registry order."""
        return tuple(self.roles_by_key.values())

    def get_object_type(self, object_type: str) -> OntologyObjectTypeDefinition | None:
        """Return one object-type definition by API name."""
        return self.object_types_by_key.get(object_type)
