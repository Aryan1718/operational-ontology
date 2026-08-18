"""Shared MCP server construction for HTTP and stdio transports."""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from app.core.config import Settings


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
            "Operational Ontology MCP foundation. Phase 1 exposes only protocol-level "
            "server metadata while later increments add approved ontology tools through "
            "the shared ontology runtime and authorization service."
        ),
    )


def create_mcp_server(settings: Settings) -> FastMCP:
    """Create the shared MCP server used by both HTTP and stdio transports."""
    definition = get_mcp_server_definition()
    return FastMCP(
        definition.name,
        instructions=definition.instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
