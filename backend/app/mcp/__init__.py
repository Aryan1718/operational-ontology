"""MCP server package."""

from app.mcp.auth import (
    build_http_identity_resolver,
    build_stdio_development_identity_resolver,
)
from app.mcp.server import create_mcp_server, get_mcp_server_definition
from app.mcp.transport import build_mcp_http_app

__all__ = [
    "build_http_identity_resolver",
    "build_mcp_http_app",
    "build_stdio_development_identity_resolver",
    "create_mcp_server",
    "get_mcp_server_definition",
]
