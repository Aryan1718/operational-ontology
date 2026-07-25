"""Ontology metadata schemas."""



from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ontology.actor_context import (
    ActorType,
    AuditView,
    AuthorizationCapability,
    AuthorizationResourceType,
    InvocationSource,
    OntologyRole,
)


class OntologyBaseModel(BaseModel):

    """Base model for ontology metadata responses."""



    model_config = ConfigDict(extra="allow", frozen=True)





class OntologyIdentity(OntologyBaseModel):

    """Top-level ontology metadata."""



    key: str

    displayName: str

    description: str | None = None

    version: str | None = None

    metadataFormatVersion: str | None = None





class OntologySourceDefinition(OntologyBaseModel):

    """Backing source mapping for an ontology object.



    ``primaryKeyColumn`` refers to the relational primary key column on the

    backing table. Public ontology object identity is defined separately by the

    object type's ``primaryKeyProperty``.

    """



    table: str

    primaryKeyColumn: str

    rowFilter: dict[str, Any] | None = None





class OntologyPropertyDefinition(OntologyBaseModel):

    """Stored property definition for an ontology object type."""



    sourceColumn: str

    type: str

    required: bool

    readOnly: bool

    enum: str | None = None

    searchable: bool = False

    filterable: bool = False

    sortable: bool = False





class OntologyObjectTypeDefinition(OntologyBaseModel):

    """Ontology object-type metadata exposed through the API."""



    key: str

    displayName: str

    pluralDisplayName: str | None = None

    description: str | None = None

    source: OntologySourceDefinition

    primaryKeyProperty: str

    titleProperty: str

    readOnly: bool | None = None

    storedProperties: dict[str, OntologyPropertyDefinition] = Field(

        default_factory=dict

    )

    links: list[str] = Field(default_factory=list)

    functions: list[str] = Field(default_factory=list)

    actions: list[str] = Field(default_factory=list)

    permissions: dict[str, Any] = Field(default_factory=dict)





class OntologyLinkStorageDefinition(OntologyBaseModel):

    """Stored link backing metadata."""



    table: str

    sourceColumn: str

    rowFilter: dict[str, Any] | None = None





class OntologyLinkTypeDefinition(OntologyBaseModel):

    """Ontology link-type metadata exposed through the API."""



    key: str

    displayName: str

    description: str | None = None

    kind: str

    sourceObjectType: str

    targetObjectType: str

    cardinality: str

    direction: str

    sourceJoinProperty: str | None = None

    targetJoinProperty: str | None = None

    storage: OntologyLinkStorageDefinition | None = None

    inverseLinkKey: str | None = None

    path: list[str] = Field(default_factory=list)





class OntologyFunctionDefinition(OntologyBaseModel):

    """Ontology function metadata exposed through the API."""



    key: str | None = None

    displayName: str | None = None

    description: str | None = None

    handler: str | None = None

    readOnly: bool | None = None

    inputModel: str | None = None

    outputModel: str | None = None





class OntologyActionTypeDefinition(OntologyBaseModel):

    """Ontology action-type metadata exposed through the API."""



    key: str | None = None

    displayName: str | None = None

    description: str | None = None

    handler: str | None = None

    targetObjectType: str | None = None





class OntologyRoleDefinition(OntologyBaseModel):

    """Ontology role metadata exposed through the API."""



    key: OntologyRole | None = None

    displayName: str | None = None

    description: str | None = None





class OntologyAuthorizationObligationsDefinition(OntologyBaseModel):

    """Allowed authorization obligations emitted by permission policies."""



    projectionKey: str | None = None

    auditView: AuditView | None = None





class OntologyPermissionRuleDefinition(OntologyBaseModel):

    """One explicit resource policy declared in ontology metadata."""



    capability: AuthorizationCapability

    resourceType: AuthorizationResourceType

    resourceKey: str

    allowedRoles: list[OntologyRole] = Field(default_factory=list)

    deniedRoles: list[OntologyRole] = Field(default_factory=list)

    allowedActorTypes: list[ActorType] = Field(default_factory=list)

    deniedActorTypes: list[ActorType] = Field(default_factory=list)

    allowedInvocationSources: list[InvocationSource] = Field(default_factory=list)

    deniedInvocationSources: list[InvocationSource] = Field(default_factory=list)

    requireInternalDispatch: bool = False

    allowedParentActionKeys: list[str] = Field(default_factory=list)

    obligations: OntologyAuthorizationObligationsDefinition | None = None

    roleObligations: dict[OntologyRole, OntologyAuthorizationObligationsDefinition] = (

        Field(default_factory=dict)

    )





class OntologyObjectTypePermissionDefaults(OntologyBaseModel):

    """Default object-type policies expanded for every registered object type."""



    list: OntologyPermissionRuleDefinition

    search: OntologyPermissionRuleDefinition

    read: OntologyPermissionRuleDefinition





class OntologyLinkTypePermissionDefaults(OntologyBaseModel):

    """Default link-type policies expanded for every registered link type."""



    traverse: OntologyPermissionRuleDefinition





class OntologyPermissionModelDefinition(OntologyBaseModel):

    """Top-level permission model configuration."""



    version: str

    defaultEffect: Literal["deny"]





class OntologyPermissionsDefinition(OntologyBaseModel):

    """Permission metadata loaded from the ontology source of truth."""



    permissionModel: OntologyPermissionModelDefinition

    objectTypeDefaults: OntologyObjectTypePermissionDefaults | None = None

    linkTypeDefaults: OntologyLinkTypePermissionDefaults | None = None

    policies: list[OntologyPermissionRuleDefinition] = Field(default_factory=list)





class OntologySummaryResponse(BaseModel):

    """Concise ontology summary for discovery endpoints."""



    key: str | None = None

    displayName: str | None = None

    version: str | None = None

    objectTypeCount: int

    linkTypeCount: int

    functionCount: int

    actionTypeCount: int

    roleCount: int





class OntologyObjectTypeCollectionResponse(BaseModel):

    """Response wrapper for object-type metadata collections."""



    items: list[OntologyObjectTypeDefinition]

    count: int





class OntologyLinkTypeCollectionResponse(BaseModel):

    """Response wrapper for link-type metadata collections."""



    items: list[OntologyLinkTypeDefinition]

    count: int





class OntologyFunctionCollectionResponse(BaseModel):

    """Response wrapper for ontology function metadata collections."""



    items: list[OntologyFunctionDefinition]

    count: int





class OntologyActionTypeCollectionResponse(BaseModel):

    """Response wrapper for ontology action-type metadata collections."""



    items: list[OntologyActionTypeDefinition]

    count: int





class OntologyRoleCollectionResponse(BaseModel):

    """Response wrapper for ontology role metadata collections."""



    items: list[OntologyRoleDefinition]

    count: int

