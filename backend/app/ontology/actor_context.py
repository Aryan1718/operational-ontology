from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActorType(StrEnum):
    """Trusted actor identity type."""

    HUMAN = "human"
    AI_AGENT = "ai_agent"
    SERVICE = "service"


class InvocationSource(StrEnum):
    """Trusted invocation channel for an ontology operation."""

    WEB_APP = "web_app"
    API = "api"
    MCP = "mcp"
    AI_WORKFLOW = "ai_workflow"
    BACKGROUND_JOB = "background_job"
    INTERNAL = "internal"


class OntologyRole(StrEnum):
    """Version 1 ontology roles."""

    VIEWER = "Viewer"
    PLANNER = "Planner"
    OPERATIONS_MANAGER = "OperationsManager"
    ADMIN = "Admin"
    AI_AGENT = "AIAgent"


class AuthorizationCapability(StrEnum):
    """Ontology capabilities evaluated by the authorization service."""

    ONTOLOGY_METADATA_READ = "ontology.metadata.read"
    ONTOLOGY_METADATA_PUBLISH = "ontology.metadata.publish"
    PERMISSION_METADATA_READ = "permission.metadata.read"
    OBJECT_LIST = "object.list"
    OBJECT_SEARCH = "object.search"
    OBJECT_READ = "object.read"
    PROPERTY_READ = "property.read"
    LINK_TRAVERSE = "link.traverse"
    FUNCTION_EXECUTE = "function.execute"
    ACTION_EXECUTE = "action.execute"
    AUDIT_READ = "audit.read"
    AUDIT_READ_FULL = "audit.read.full"


class AuthorizationResourceType(StrEnum):
    """Ontology resource categories protected by authorization."""

    ONTOLOGY = "ontology"
    OBJECT_TYPE = "objectType"
    OBJECT = "object"
    PROPERTY = "property"
    LINK_TYPE = "linkType"
    FUNCTION = "function"
    ACTION = "action"
    AUDIT_LOG = "auditLog"


class AuthorizationReasonCode(StrEnum):
    """Internal allow and deny reason codes."""

    ALLOWED = "ALLOWED"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    ACTOR_INACTIVE = "ACTOR_INACTIVE"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    ROLE_NOT_ALLOWED = "ROLE_NOT_ALLOWED"
    ACTOR_TYPE_NOT_ALLOWED = "ACTOR_TYPE_NOT_ALLOWED"
    INVOCATION_SOURCE_NOT_ALLOWED = "INVOCATION_SOURCE_NOT_ALLOWED"
    RESOURCE_NOT_ALLOWED = "RESOURCE_NOT_ALLOWED"
    PROPERTY_NOT_ALLOWED = "PROPERTY_NOT_ALLOWED"
    INTERNAL_DISPATCH_REQUIRED = "INTERNAL_DISPATCH_REQUIRED"
    INVALID_INTERNAL_DISPATCH = "INVALID_INTERNAL_DISPATCH"
    EXPLICITLY_DENIED = "EXPLICITLY_DENIED"


class AuditView(StrEnum):
    """Supported audit response views."""

    SUMMARY = "summary"
    OBJECT_HISTORY = "object_history"
    OPERATIONAL = "operational"
    FULL = "full"


class AuthorizationModel(BaseModel):
    """Frozen base model for internal authorization contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ActorContext(AuthorizationModel):
    """Trusted actor context derived from authentication or internal runtime code."""

    actor_id: str = Field(min_length=1)
    actor_type: ActorType
    roles: tuple[OntologyRole, ...] = Field(default_factory=tuple)
    invocation_source: InvocationSource

    @field_validator("roles", mode="before")
    @classmethod
    def _normalize_roles(cls, value: object) -> tuple[OntologyRole, ...]:
        if value is None:
            return ()
        roles = tuple(OntologyRole(item) for item in value)
        return tuple(dict.fromkeys(roles))


class AuthorizationResource(AuthorizationModel):
    """Concrete ontology resource under authorization."""

    resource_type: AuthorizationResourceType
    resource_key: str = Field(min_length=1)
    object_id: str | None = None
    property_key: str | None = None


class TrustedAuthorizationContext(AuthorizationModel):
    """Trusted internal context that must never come from public request input."""

    internal_dispatch: bool = False
    parent_action_key: str | None = None
    parent_execution_id: str | None = None


class AuthorizationRequest(AuthorizationModel):
    """One authorization evaluation request."""

    actor: ActorContext
    capability: AuthorizationCapability
    resource: AuthorizationResource
    trusted_context: TrustedAuthorizationContext | None = None


class AuthorizationObligations(AuthorizationModel):
    """Obligations the caller must enforce after authorization succeeds."""

    projection_key: str | None = None
    audit_view: AuditView | None = None


class AuthorizationDecision(AuthorizationModel):
    """Authorization result returned by the central service."""

    allowed: bool
    reason_code: AuthorizationReasonCode
    policy_version: str
    matched_role: OntologyRole | None = None
    obligations: AuthorizationObligations | None = None
