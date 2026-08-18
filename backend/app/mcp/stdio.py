"""Stdio entrypoint for local MCP development and MCP Inspector."""

from __future__ import annotations

from app.core.config import get_settings
from app.mcp.auth import build_stdio_development_identity_resolver
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor
from app.mcp.server import create_mcp_server


def main() -> None:
    """Run the shared MCP server over stdio with an explicit dev AI identity."""
    settings = get_settings()
    actor = build_stdio_development_identity_resolver(settings).resolve_actor()
    server = create_mcp_server(settings)
    token = set_current_mcp_actor(actor)
    try:
        server.run(transport="stdio")
    finally:
        reset_current_mcp_actor(token)


if __name__ == "__main__":
    main()
