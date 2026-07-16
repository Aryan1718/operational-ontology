"""Immutable permission-policy lookup derived from ontology metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.ontology.actor_context import (
    ActorType,
    AuthorizationCapability,
    AuthorizationObligations,
    AuthorizationResourceType,
    InvocationSource,
    OntologyRole,
)
from app.ontology.validator import OntologyValidationError
from app.schemas.ontology import (
    OntologyActionTypeDefinition,
    OntologyFunctionDefinition,
    OntologyIdentity,
    OntologyLinkTypeDefinition,
    OntologyObjectTypeDefinition,
    OntologyPermissionRuleDefinition,
    OntologyPermissionsDefinition,
    OntologyRoleDefinition,
)


@dataclass(frozen=True)
class PermissionPolicy:
    """One normalized immutable permission policy."""

    policy_key: str
    capability: AuthorizationCapability
    resource_type: AuthorizationResourceType
    resource_key: str
    allowed_roles: frozenset[OntologyRole]
    denied_roles: frozenset[OntologyRole]
    allowed_actor_types: frozenset[ActorType]
    denied_actor_types: frozenset[ActorType]
    allowed_invocation_sources: frozenset[InvocationSource]
    denied_invocation_sources: frozenset[InvocationSource]
    require_internal_dispatch: bool
    allowed_parent_action_keys: frozenset[str]
    obligations: AuthorizationObligations | None
    role_obligations: Mapping[OntologyRole, AuthorizationObligations]


@dataclass(frozen=True)
class PermissionRegistry:
    """Immutable in-memory permission registry built at startup."""

    policy_version: str
    default_effect: str
    policies_by_key: Mapping[str, PermissionPolicy]
    known_resource_keys_by_type: Mapping[AuthorizationResourceType, frozenset[str]]
    known_capabilities: frozenset[AuthorizationCapability]

    @classmethod
    def from_ontology(
        cls,
        *,
        ontology: OntologyIdentity,
        object_types_by_key: Mapping[str, OntologyObjectTypeDefinition],
        link_types_by_key: Mapping[str, OntologyLinkTypeDefinition],
        functions_by_key: Mapping[str, OntologyFunctionDefinition],
        action_types_by_key: Mapping[str, OntologyActionTypeDefinition],
        roles_by_key: Mapping[str, OntologyRoleDefinition],
        permissions: OntologyPermissionsDefinition,
    ) -> "PermissionRegistry":
        if permissions.permissionModel.defaultEffect != "deny":
            raise OntologyValidationError(
                "Ontology permissionModel.defaultEffect must be 'deny'."
            )

        known_roles = frozenset(OntologyRole(role_key) for role_key in roles_by_key)
        expanded_policies = [
            *cls._expand_object_type_defaults(
                object_types_by_key=object_types_by_key,
                defaults=permissions.objectTypeDefaults,
            ),
            *cls._expand_link_type_defaults(
                link_types_by_key=link_types_by_key,
                defaults=permissions.linkTypeDefaults,
            ),
            *permissions.policies,
        ]

        policies_by_key: dict[str, PermissionPolicy] = {}
        known_resource_keys = cls._build_known_resource_keys(
            ontology_key=ontology.key,
            object_types_by_key=object_types_by_key,
            link_types_by_key=link_types_by_key,
            functions_by_key=functions_by_key,
            action_types_by_key=action_types_by_key,
            explicit_policies=permissions.policies,
        )

        for definition in expanded_policies:
            cls._validate_policy_definition(
                definition=definition,
                known_roles=known_roles,
                ontology_key=ontology.key,
                object_types_by_key=object_types_by_key,
                link_types_by_key=link_types_by_key,
                functions_by_key=functions_by_key,
                action_types_by_key=action_types_by_key,
                explicit_known_resources=known_resource_keys,
            )
            policy_key = cls.build_policy_key(
                definition.capability,
                definition.resourceType,
                definition.resourceKey,
            )
            if policy_key in policies_by_key:
                raise OntologyValidationError(
                    f"Duplicate normalized permission policy key '{policy_key}'."
                )
            policies_by_key[policy_key] = cls._freeze_policy(definition)

        return cls(
            policy_version=permissions.permissionModel.version,
            default_effect=permissions.permissionModel.defaultEffect,
            policies_by_key=MappingProxyType(policies_by_key),
            known_resource_keys_by_type=MappingProxyType(
                {
                    resource_type: frozenset(sorted(resource_keys))
                    for resource_type, resource_keys in known_resource_keys.items()
                }
            ),
            known_capabilities=frozenset(
                policy.capability for policy in policies_by_key.values()
            ),
        )

    @staticmethod
    def build_policy_key(
        capability: AuthorizationCapability,
        resource_type: AuthorizationResourceType,
        resource_key: str,
    ) -> str:
        """Build a deterministic normalized policy lookup key."""
        return f"{capability.value}:{resource_type.value}:{resource_key}"

    @staticmethod
    def normalize_resource_key(
        *,
        resource_type: AuthorizationResourceType,
        resource_key: str,
        property_key: str | None = None,
    ) -> str:
        """Normalize request resource identity to the policy lookup key format."""
        if resource_type is AuthorizationResourceType.PROPERTY and property_key:
            return f"{resource_key}.{property_key}"
        return resource_key

    def get_policy(
        self,
        capability: AuthorizationCapability,
        resource_type: AuthorizationResourceType,
        resource_key: str,
    ) -> PermissionPolicy | None:
        """Return one normalized policy or ``None`` when no policy exists."""
        return self.policies_by_key.get(
            self.build_policy_key(capability, resource_type, resource_key)
        )

    def is_known_resource(
        self,
        resource_type: AuthorizationResourceType,
        resource_key: str,
    ) -> bool:
        """Return whether the ontology registry recognizes the resource identity."""
        return resource_key in self.known_resource_keys_by_type.get(resource_type, frozenset())

    @classmethod
    def _expand_object_type_defaults(
        cls,
        *,
        object_types_by_key: Mapping[str, OntologyObjectTypeDefinition],
        defaults: object | None,
    ) -> list[OntologyPermissionRuleDefinition]:
        if defaults is None:
            return []
        policies: list[OntologyPermissionRuleDefinition] = []
        templates = (
            defaults.list,
            defaults.search,
            defaults.read,
        )
        for object_type_key in object_types_by_key:
            for template in templates:
                policies.append(
                    template.model_copy(
                        update={
                            "resourceType": AuthorizationResourceType.OBJECT_TYPE,
                            "resourceKey": object_type_key,
                        }
                    )
                )
        return policies

    @classmethod
    def _expand_link_type_defaults(
        cls,
        *,
        link_types_by_key: Mapping[str, OntologyLinkTypeDefinition],
        defaults: object | None,
    ) -> list[OntologyPermissionRuleDefinition]:
        if defaults is None:
            return []
        policies: list[OntologyPermissionRuleDefinition] = []
        for link_type_key in link_types_by_key:
            policies.append(
                defaults.traverse.model_copy(
                    update={
                        "resourceType": AuthorizationResourceType.LINK_TYPE,
                        "resourceKey": link_type_key,
                    }
                )
            )
        return policies

    @classmethod
    def _build_known_resource_keys(
        cls,
        *,
        ontology_key: str,
        object_types_by_key: Mapping[str, OntologyObjectTypeDefinition],
        link_types_by_key: Mapping[str, OntologyLinkTypeDefinition],
        functions_by_key: Mapping[str, OntologyFunctionDefinition],
        action_types_by_key: Mapping[str, OntologyActionTypeDefinition],
        explicit_policies: list[OntologyPermissionRuleDefinition],
    ) -> dict[AuthorizationResourceType, set[str]]:
        known_resources: dict[AuthorizationResourceType, set[str]] = {
            AuthorizationResourceType.ONTOLOGY: {ontology_key},
            AuthorizationResourceType.OBJECT_TYPE: set(object_types_by_key),
            AuthorizationResourceType.OBJECT: set(object_types_by_key),
            AuthorizationResourceType.PROPERTY: set(),
            AuthorizationResourceType.LINK_TYPE: set(link_types_by_key),
            AuthorizationResourceType.FUNCTION: set(functions_by_key),
            AuthorizationResourceType.ACTION: set(action_types_by_key),
            AuthorizationResourceType.AUDIT_LOG: set(),
        }
        for definition in explicit_policies:
            if definition.resourceType is AuthorizationResourceType.AUDIT_LOG:
                known_resources[AuthorizationResourceType.AUDIT_LOG].add(
                    definition.resourceKey
                )
            if definition.resourceType is AuthorizationResourceType.PROPERTY:
                known_resources[AuthorizationResourceType.PROPERTY].add(
                    definition.resourceKey
                )
        return known_resources

    @classmethod
    def _validate_policy_definition(
        cls,
        *,
        definition: OntologyPermissionRuleDefinition,
        known_roles: frozenset[OntologyRole],
        ontology_key: str,
        object_types_by_key: Mapping[str, OntologyObjectTypeDefinition],
        link_types_by_key: Mapping[str, OntologyLinkTypeDefinition],
        functions_by_key: Mapping[str, OntologyFunctionDefinition],
        action_types_by_key: Mapping[str, OntologyActionTypeDefinition],
        explicit_known_resources: Mapping[AuthorizationResourceType, set[str]],
    ) -> None:
        referenced_roles = set(definition.allowedRoles)
        referenced_roles.update(definition.deniedRoles)
        referenced_roles.update(definition.roleObligations)
        unknown_roles = sorted(role.value for role in referenced_roles.difference(known_roles))
        if unknown_roles:
            raise OntologyValidationError(
                "Permission policy references unknown roles: "
                + ", ".join(unknown_roles)
                + "."
            )

        resource_type = definition.resourceType
        resource_key = definition.resourceKey
        if resource_type is AuthorizationResourceType.ONTOLOGY:
            if resource_key != ontology_key:
                raise OntologyValidationError(
                    f"Permission policy references unknown ontology resource '{resource_key}'."
                )
            return
        if resource_type in (
            AuthorizationResourceType.OBJECT_TYPE,
            AuthorizationResourceType.OBJECT,
        ):
            if resource_key not in object_types_by_key:
                raise OntologyValidationError(
                    f"Permission policy references unknown object type '{resource_key}'."
                )
            return
        if resource_type is AuthorizationResourceType.LINK_TYPE:
            if resource_key not in link_types_by_key:
                raise OntologyValidationError(
                    f"Permission policy references unknown link type '{resource_key}'."
                )
            return
        if resource_type is AuthorizationResourceType.FUNCTION:
            if resource_key not in functions_by_key:
                raise OntologyValidationError(
                    f"Permission policy references unknown function '{resource_key}'."
                )
            return
        if resource_type is AuthorizationResourceType.ACTION:
            if resource_key not in action_types_by_key:
                raise OntologyValidationError(
                    f"Permission policy references unknown action '{resource_key}'."
                )
            return
        if resource_type is AuthorizationResourceType.PROPERTY:
            object_type_key, separator, property_key = resource_key.partition(".")
            if not separator:
                raise OntologyValidationError(
                    "Property permission policy keys must use 'ObjectType.propertyKey'."
                )
            object_type = object_types_by_key.get(object_type_key)
            if object_type is None or property_key not in object_type.storedProperties:
                raise OntologyValidationError(
                    f"Permission policy references unknown property '{resource_key}'."
                )
            return
        if resource_type is AuthorizationResourceType.AUDIT_LOG:
            if resource_key not in explicit_known_resources[AuthorizationResourceType.AUDIT_LOG]:
                raise OntologyValidationError(
                    f"Permission policy references unknown audit resource '{resource_key}'."
                )

    @staticmethod
    def _freeze_policy(definition: OntologyPermissionRuleDefinition) -> PermissionPolicy:
        obligations = None
        if definition.obligations is not None:
            obligations = AuthorizationObligations(
                projection_key=definition.obligations.projectionKey,
                audit_view=definition.obligations.auditView,
            )
        role_obligations = MappingProxyType(
            {
                role: AuthorizationObligations(
                    projection_key=role_obligation.projectionKey,
                    audit_view=role_obligation.auditView,
                )
                for role, role_obligation in definition.roleObligations.items()
            }
        )
        return PermissionPolicy(
            policy_key=PermissionRegistry.build_policy_key(
                definition.capability,
                definition.resourceType,
                definition.resourceKey,
            ),
            capability=definition.capability,
            resource_type=definition.resourceType,
            resource_key=definition.resourceKey,
            allowed_roles=frozenset(definition.allowedRoles),
            denied_roles=frozenset(definition.deniedRoles),
            allowed_actor_types=frozenset(definition.allowedActorTypes),
            denied_actor_types=frozenset(definition.deniedActorTypes),
            allowed_invocation_sources=frozenset(definition.allowedInvocationSources),
            denied_invocation_sources=frozenset(definition.deniedInvocationSources),
            require_internal_dispatch=definition.requireInternalDispatch,
            allowed_parent_action_keys=frozenset(definition.allowedParentActionKeys),
            obligations=obligations,
            role_obligations=role_obligations,
        )
