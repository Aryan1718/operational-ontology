"""Pydantic schemas for MCP ontology object tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.objects import (
    AggregateLinkedObjectsResponse,
    LinkedObjectsResponse,
    ObjectSearchRequest,
    ObjectSearchResponse,
    OntologyObjectResponse,
)


class SearchObjectsInput(ObjectSearchRequest):
    """MCP input for one ontology object-type search."""

    objectType: str = Field(min_length=1)


class GetObjectInput(BaseModel):
    """MCP input for one ontology object lookup."""

    objectType: str = Field(min_length=1)
    objectId: str = Field(min_length=1)


class GetLinkedObjectsInput(GetObjectInput):
    """MCP input for one linked-object traversal."""

    linkType: str | None = Field(default=None, min_length=1)


class McpEvidenceObject(BaseModel):
    """Compact evidence reference surfaced to MCP clients."""

    objectType: str
    objectId: str
    title: str | None = None
    href: str


class McpToolMeta(BaseModel):
    """Shared metadata returned by every MCP ontology tool."""

    toolName: str
    requestId: str
    ontologyVersion: str | None = None
    permissionPolicyVersion: str | None = None
    executedAt: str
    nextCursor: str | None = None
    hasMore: bool | None = None


class McpToolResult(BaseModel):
    """Standard structured result for ontology MCP tools."""

    data: ObjectSearchResponse | OntologyObjectResponse | LinkedObjectsResponse | AggregateLinkedObjectsResponse
    evidence: list[McpEvidenceObject] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    meta: McpToolMeta


class McpToolErrorPayload(BaseModel):
    """Structured safe error payload encoded into MCP tool failures."""

    code: str
    message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)
    toolName: str
    requestId: str
