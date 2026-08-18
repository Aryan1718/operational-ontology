"""HTTP transport helpers for mounting the MCP server into FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from app.mcp.auth import HttpMcpIdentityResolver, McpAuthenticationError
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor


class AuthenticatedMcpHttpApp:
    """ASGI wrapper that enforces MCP bearer authentication before dispatch."""

    def __init__(self, app: Any, identity_resolver: HttpMcpIdentityResolver) -> None:
        self._app = app
        self._identity_resolver = identity_resolver

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        authorization_header = Headers(scope=scope).get("authorization")
        try:
            actor = await self._identity_resolver.resolve_actor(authorization_header)
        except McpAuthenticationError as exc:
            response = JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": "MCP_AUTHENTICATION_FAILED",
                        "message": exc.message,
                    }
                },
            )
            await response(scope, receive, send)
            return

        token = set_current_mcp_actor(actor)
        try:
            await self._app(scope, receive, send)
        finally:
            reset_current_mcp_actor(token)


def build_mcp_http_app(server: Any, identity_resolver: HttpMcpIdentityResolver) -> Any:
    """Return the authenticated ASGI app mounted at `/mcp`."""
    return AuthenticatedMcpHttpApp(
        server.streamable_http_app(),
        identity_resolver,
    )
