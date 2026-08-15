"""MCP server entrypoint for ontology read tools."""

from __future__ import annotations

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from app.db.session import get_session_factory
from app.schemas.objects import ObjectSearchFilter, ObjectSearchSort

from app.mcp.tool_adapter import (
    McpToolExecutionError,
    OntologyMcpToolAdapter,
    format_tool_error,
)


def create_mcp_server(application: FastAPI) -> FastMCP:
    """Create and register the ontology MCP server."""

    server = FastMCP(
        "Operational Ontology",
        instructions=(
            "Read ontology-backed operational objects and declared links using the "
            "shared runtime and authorization services."
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )

    def build_adapter() -> OntologyMcpToolAdapter:
        return OntologyMcpToolAdapter(
            registry=application.state.ontology_registry,
            authorization_service=application.state.authorization_service,
            session_factory=get_session_factory(),
        )

    @server.tool(name="searchObjects")
    def search_objects(
        objectType: str,
        query: str | None = None,
        filters: list[ObjectSearchFilter] | None = None,
        sort: list[ObjectSearchSort] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, object]:
        """Search one ontology object type using the existing object search path."""

        try:
            return build_adapter().search_objects(
                tool_input={
                    "objectType": objectType,
                    "query": query,
                    "filters": filters,
                    "sort": sort,
                    "limit": limit,
                    "cursor": cursor,
                }
            )
        except McpToolExecutionError as exc:
            raise RuntimeError(format_tool_error(exc)) from exc

    @server.tool(name="getObject")
    def get_object(
        objectType: str,
        objectId: str,
    ) -> dict[str, object]:
        """Return one ontology object using the existing object lookup path."""

        try:
            return build_adapter().get_object(
                tool_input={
                    "objectType": objectType,
                    "objectId": objectId,
                }
            )
        except McpToolExecutionError as exc:
            raise RuntimeError(format_tool_error(exc)) from exc

    @server.tool(name="getLinkedObjects")
    def get_linked_objects(
        objectType: str,
        objectId: str,
        linkType: str | None = None,
    ) -> dict[str, object]:
        """Return linked ontology objects using the existing declared link path."""

        try:
            return build_adapter().get_linked_objects(
                tool_input={
                    "objectType": objectType,
                    "objectId": objectId,
                    "linkType": linkType,
                }
            )
        except McpToolExecutionError as exc:
            raise RuntimeError(format_tool_error(exc)) from exc

    return server
