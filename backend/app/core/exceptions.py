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
        super().__init__(self.message)


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
