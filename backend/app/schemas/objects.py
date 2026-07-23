"""Object API schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class OntologyObjectResponse(BaseModel):
    """Generic one-object ontology response."""

    objectType: str
    objectId: str
    displayName: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class OntologyObjectReference(BaseModel):
    """Minimal public reference to one ontology object."""

    objectType: str
    objectId: str


class LinkedObjectsResponse(BaseModel):
    """Linked-object traversal response."""

    source: OntologyObjectReference
    linkType: str
    targetObjectType: str
    cardinality: str
    objects: list[OntologyObjectResponse] = Field(default_factory=list)


class AggregateLinkObjectsResponse(BaseModel):
    """Aggregate response entry for one declared link."""

    linkType: str
    targetObjectType: str
    cardinality: str
    resolutionStatus: Literal["resolved", "notImplemented"]
    objects: list[OntologyObjectResponse] = Field(default_factory=list)


class AggregateLinkedObjectsResponse(BaseModel):
    """Aggregate linked-object traversal response."""

    source: OntologyObjectReference
    links: list[AggregateLinkObjectsResponse] = Field(default_factory=list)


class ObjectSearchFilter(BaseModel):
    """Validated one-property structured filter."""

    property: str
    operator: Literal[
        "equals",
        "notEquals",
        "in",
        "contains",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
    ]
    value: Any


class ObjectSearchSort(BaseModel):
    """Validated one-property sort instruction."""

    property: str
    direction: Literal["asc", "desc"]


class ObjectSearchRequest(BaseModel):
    """Single-object-type ontology search request."""

    query: str | None = None
    filters: list[ObjectSearchFilter] | None = None
    sort: list[ObjectSearchSort] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Query must not be empty.")
        return normalized


class ObjectSearchResponse(BaseModel):
    """Single-object-type ontology search response payload."""

    objectType: str
    objects: list[OntologyObjectResponse] = Field(default_factory=list)
