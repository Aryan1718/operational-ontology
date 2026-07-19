"""Object API schemas."""

from typing import Any

from pydantic import BaseModel, Field


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
