"""Central ontology authorization service."""

from __future__ import annotations

from app.core.exceptions import AuthorizationDeniedError
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    AuthorizationDecision,
    AuthorizationReasonCode,
    AuthorizationRequest,
    AuthorizationResourceType,
    OntologyRole,
)
from app.ontology.permission_registry import PermissionPolicy, PermissionRegistry


class AuthorizationService:
    """Evaluate all ontology authorization decisions from one immutable registry."""

    def __init__(self, permission_registry: PermissionRegistry) -> None:
        self._permission_registry = permission_registry

    @property
    def permission_registry(self) -> PermissionRegistry:
        """Expose the immutable permission registry used by this service."""
        return self._permission_registry

    def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Return an allow or deny decision without raising exceptions."""
        policy_version = self._permission_registry.policy_version
        actor = request.actor
        if not actor.actor_id:
            return self._deny(
                AuthorizationReasonCode.NOT_AUTHENTICATED,
                policy_version=policy_version,
            )

        normalized_resource_key = self._permission_registry.normalize_resource_key(
            resource_type=request.resource.resource_type,
            resource_key=request.resource.resource_key,
            property_key=request.resource.property_key,
        )
        known_resource = self._permission_registry.is_known_resource(
            request.resource.resource_type,
            normalized_resource_key,
        )
        if request.resource.resource_type is AuthorizationResourceType.PROPERTY and not request.resource.property_key:
            return self._deny(
                AuthorizationReasonCode.PROPERTY_NOT_ALLOWED,
                policy_version=policy_version,
            )
        if not known_resource:
            return self._deny(
                self._unknown_resource_reason(request.resource.resource_type),
                policy_version=policy_version,
            )

        policy = self._permission_registry.get_policy(
            request.capability,
            request.resource.resource_type,
            normalized_resource_key,
        )
        if policy is None:
            return self._deny(
                AuthorizationReasonCode.POLICY_NOT_FOUND,
                policy_version=policy_version,
            )

        if actor.actor_type is ActorType.SERVICE and ActorType.SERVICE not in policy.allowed_actor_types:
            return self._deny(
                AuthorizationReasonCode.ACTOR_TYPE_NOT_ALLOWED,
                policy_version=policy_version,
            )
        if actor.actor_type in policy.denied_actor_types:
            return self._deny(
                AuthorizationReasonCode.ACTOR_TYPE_NOT_ALLOWED,
                policy_version=policy_version,
            )
        if policy.allowed_actor_types and actor.actor_type not in policy.allowed_actor_types:
            return self._deny(
                AuthorizationReasonCode.ACTOR_TYPE_NOT_ALLOWED,
                policy_version=policy_version,
            )
        if actor.invocation_source in policy.denied_invocation_sources:
            return self._deny(
                AuthorizationReasonCode.INVOCATION_SOURCE_NOT_ALLOWED,
                policy_version=policy_version,
            )
        if (
            policy.allowed_invocation_sources
            and actor.invocation_source not in policy.allowed_invocation_sources
        ):
            return self._deny(
                AuthorizationReasonCode.INVOCATION_SOURCE_NOT_ALLOWED,
                policy_version=policy_version,
            )

        effective_roles = self._effective_roles(actor)
        if policy.denied_roles.intersection(effective_roles):
            return self._deny(
                AuthorizationReasonCode.EXPLICITLY_DENIED,
                policy_version=policy_version,
            )

        matched_role = self._match_allowed_role(actor, effective_roles, policy)
        if matched_role is None:
            return self._deny(
                AuthorizationReasonCode.ROLE_NOT_ALLOWED,
                policy_version=policy_version,
            )

        trusted_context = request.trusted_context
        if policy.require_internal_dispatch:
            if trusted_context is None or not trusted_context.internal_dispatch:
                return self._deny(
                    AuthorizationReasonCode.INTERNAL_DISPATCH_REQUIRED,
                    policy_version=policy_version,
                )
            if (
                not trusted_context.parent_action_key
                or not trusted_context.parent_execution_id
            ):
                return self._deny(
                    AuthorizationReasonCode.INVALID_INTERNAL_DISPATCH,
                    policy_version=policy_version,
                )
            if (
                policy.allowed_parent_action_keys
                and trusted_context.parent_action_key
                not in policy.allowed_parent_action_keys
            ):
                return self._deny(
                    AuthorizationReasonCode.INVALID_INTERNAL_DISPATCH,
                    policy_version=policy_version,
                )

        obligations = policy.role_obligations.get(matched_role, policy.obligations)
        return AuthorizationDecision(
            allowed=True,
            reason_code=AuthorizationReasonCode.ALLOWED,
            policy_version=policy_version,
            matched_role=matched_role,
            obligations=obligations,
        )

    def authorize_or_raise(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Return an allow decision or raise the shared safe public exception."""
        decision = self.authorize(request)
        if decision.allowed:
            return decision
        raise AuthorizationDeniedError(
            decision=decision,
            capability=request.capability,
            resource_type=request.resource.resource_type,
            resource_key=self._permission_registry.normalize_resource_key(
                resource_type=request.resource.resource_type,
                resource_key=request.resource.resource_key,
                property_key=request.resource.property_key,
            ),
        )

    @staticmethod
    def _deny(
        reason_code: AuthorizationReasonCode,
        *,
        policy_version: str,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            reason_code=reason_code,
            policy_version=policy_version,
        )

    @staticmethod
    def _effective_roles(actor: ActorContext) -> tuple[OntologyRole, ...]:
        if actor.actor_type is ActorType.AI_AGENT:
            return tuple(role for role in actor.roles if role is OntologyRole.AI_AGENT)
        return actor.roles

    @staticmethod
    def _match_allowed_role(
        actor: ActorContext,
        effective_roles: tuple[OntologyRole, ...],
        policy: PermissionPolicy,
    ) -> OntologyRole | None:
        for role in actor.roles:
            if role in effective_roles and role in policy.allowed_roles:
                return role
        return None

    @staticmethod
    def _unknown_resource_reason(
        resource_type: AuthorizationResourceType,
    ) -> AuthorizationReasonCode:
        if resource_type is AuthorizationResourceType.PROPERTY:
            return AuthorizationReasonCode.PROPERTY_NOT_ALLOWED
        return AuthorizationReasonCode.RESOURCE_NOT_ALLOWED
