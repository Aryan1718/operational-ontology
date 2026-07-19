"""Shared application exceptions."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ontology.actor_context import (
    AuthorizationCapability,
    AuthorizationDecision,
    AuthorizationReasonCode,
    AuthorizationResourceType,
)


@dataclass(slots=True)
class ApplicationError(Exception):
    """Base shared application exception mapped to the API error envelope."""

    code: str
    message: str
    status_code: int
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


@dataclass(slots=True)
class AuthorizationDeniedError(ApplicationError):
    """Safe public authorization error that preserves internal denial context."""

    decision: AuthorizationDecision = field(init=False)
    capability: AuthorizationCapability = field(init=False)
    resource_type: AuthorizationResourceType = field(init=False)
    resource_key: str = field(init=False)

    def __init__(
        self,
        *,
        decision: AuthorizationDecision,
        capability: AuthorizationCapability,
        resource_type: AuthorizationResourceType,
        resource_key: str,
    ) -> None:
        self.decision = decision
        self.capability = capability
        self.resource_type = resource_type
        self.resource_key = resource_key
        if decision.reason_code is AuthorizationReasonCode.NOT_AUTHENTICATED:
            super().__init__(
                code="UNAUTHENTICATED",
                message="Authentication is required to perform this operation.",
                status_code=401,
            )
            return
        super().__init__(
            code="OPERATION_NOT_PERMITTED",
            message="You are not permitted to execute this operation.",
            status_code=403,
        )

    def log_context(self) -> dict[str, object]:
        """Return internal denial details for structured logging only."""
        return {
            "reasonCode": self.decision.reason_code.value,
            "policyVersion": self.decision.policy_version,
            "capability": self.capability.value,
            "resourceType": self.resource_type.value,
            "resourceKey": self.resource_key,
            "matchedRole": (
                self.decision.matched_role.value
                if self.decision.matched_role is not None
                else None
            ),
        }


class ObjectTypeNotFoundError(ApplicationError):
    """Raised when an ontology object type is not registered."""

    def __init__(self, object_type: str) -> None:
        super().__init__(
            code="OBJECT_TYPE_NOT_FOUND",
            message=f"Ontology object type '{object_type}' was not found.",
            status_code=404,
            details={"objectType": object_type},
        )


class ObjectNotFoundError(ApplicationError):
    """Raised when one ontology object instance cannot be found."""

    def __init__(self, object_type: str, object_id: str) -> None:
        super().__init__(
            code="OBJECT_NOT_FOUND",
            message=f"{object_type} object '{object_id}' was not found.",
            status_code=404,
            details={"objectType": object_type, "objectId": object_id},
        )


class LinkNotFoundError(ApplicationError):
    """Raised when an ontology link type cannot be traversed from a source object."""

    def __init__(self, object_type: str, link_type: str) -> None:
        super().__init__(
            code="LINK_NOT_FOUND",
            message=(
                f"Ontology link type '{link_type}' was not found for "
                f"object type '{object_type}'."
            ),
            status_code=404,
            details={"objectType": object_type, "linkType": link_type},
        )


class LinkResolutionNotImplementedError(ApplicationError):
    """Raised when a declared link kind is recognized but not implemented yet."""

    def __init__(self, link_type: str, kind: str) -> None:
        super().__init__(
            code="LINK_RESOLUTION_NOT_IMPLEMENTED",
            message=(
                f"Ontology link type '{link_type}' uses unsupported "
                f"link kind '{kind}'."
            ),
            status_code=501,
            details={"linkType": link_type, "kind": kind},
        )


class InvalidOntologyMappingError(ApplicationError):
    """Raised when trusted ontology metadata cannot be mapped safely."""

    def __init__(self, object_type: str, reason: str) -> None:
        super().__init__(
            code="INVALID_ONTOLOGY_MAPPING",
            message=(
                f"Ontology object type '{object_type}' has an invalid database mapping."
            ),
            status_code=500,
            details={"objectType": object_type, "reason": reason},
        )


class OntologyMappingError(InvalidOntologyMappingError):
    """Backward-compatible alias for invalid ontology mapping errors."""
