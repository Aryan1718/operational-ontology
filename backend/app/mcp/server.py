"""Shared MCP server construction for HTTP and stdio transports."""

from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.core.config import Settings
from app.core.exceptions import ApplicationError
from app.mcp.context import get_current_mcp_actor
from app.mcp.ontology_tool_gateway import (
    GetLinkedObjectsToolInput,
    GetObjectToolInput,
    OntologyToolGateway,
    SearchObjectsToolInput,
    build_default_ontology_tool_gateway,
)


@dataclass(frozen=True)
class McpServerDefinition:
    """Static Phase 1 MCP server metadata shared across transports."""

    name: str
    instructions: str


def get_mcp_server_definition() -> McpServerDefinition:
    """Return the single Operational Ontology MCP server definition."""
    return McpServerDefinition(
        name="Operational Ontology",
        instructions=(
            "Operational Ontology MCP foundation. Phase 2 exposes read-only object "
            "search, object retrieval, and declared link traversal through the "
            "shared ontology runtime and authorization service."
        ),
    )


def create_mcp_server(
    settings: Settings,
    *,
    ontology_tool_gateway: OntologyToolGateway | None = None,
) -> FastMCP:
    """Create the shared MCP server used by both HTTP and stdio transports."""
    del settings
    definition = get_mcp_server_definition()
    server = FastMCP(
        definition.name,
        instructions=definition.instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
    gateway = ontology_tool_gateway or build_default_ontology_tool_gateway()

    @server.tool(
        name="searchObjects",
        description=(
            "Search one ontology object type using the existing metadata-driven "
            "object runtime. This is a read-only operation."
        ),
    )
    def search_objects(payload: SearchObjectsToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.search_objects(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    @server.tool(
        name="getObject",
        description=(
            "Get one ontology object by object type and public object ID using the "
            "existing object runtime. This is a read-only operation."
        ),
    )
    def get_object(payload: GetObjectToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.get_object(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    @server.tool(
        name="getLinkedObjects",
        description=(
            "Traverse one declared ontology link from a source object using the "
            "existing link runtime. This is a read-only operation."
        ),
    )
    def get_linked_objects(payload: GetLinkedObjectsToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.get_linked_objects(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    return server


def _require_current_mcp_actor():
    actor = get_current_mcp_actor()
    if actor is None:
        raise ToolError("MCP actor context is not available.")
    return actor


def _tool_error_from_application_error(exc: ApplicationError) -> ToolError:
    return ToolError(f"{exc.code}: {exc.message}")
