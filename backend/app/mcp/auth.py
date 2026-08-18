"""Authentication boundaries for MCP transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole


class McpAuthenticationError(RuntimeError):
    """Safe MCP authentication failure."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RemoteMcpTokenVerifier(Protocol):
    """Future remote bearer-token verifier boundary for MCP HTTP requests."""

    async def verify_bearer_token(self, bearer_token: str) -> ActorContext:
        """Return a trusted AI actor derived from a verified MCP token."""


@dataclass(frozen=True)
class UnconfiguredRemoteMcpTokenVerifier:
    """Fail-closed placeholder until production MCP token validation is implemented."""

    settings: Settings

    async def verify_bearer_token(self, bearer_token: str) -> ActorContext:
        del bearer_token
        audience = self.settings.mcp_token_audience or "<unset>"
        raise McpAuthenticationError(
            f"Remote MCP authentication is not configured for audience '{audience}'."
        )


class HttpMcpIdentityResolver:
    """Resolve trusted remote MCP actors from HTTP authorization headers."""

    def __init__(self, verifier: RemoteMcpTokenVerifier) -> None:
        self._verifier = verifier

    async def resolve_actor(self, authorization_header: str | None) -> ActorContext:
        if not authorization_header:
            raise McpAuthenticationError("Bearer authentication is required.")
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise McpAuthenticationError("Bearer authentication is required.")
        actor = await self._verifier.verify_bearer_token(token)
        return _coerce_ai_agent_actor(actor, invocation_source=InvocationSource.MCP)


class StdioDevelopmentIdentityResolver:
    """Resolve the trusted development AI identity for local stdio use only."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve_actor(self) -> ActorContext:
        if not self._settings.mcp_stdio_dev_identity_enabled:
            raise McpAuthenticationError(
                "Local MCP stdio development identity is disabled.",
                status_code=403,
            )
        if self._settings.is_production:
            raise McpAuthenticationError(
                "Local MCP stdio development identity is not allowed in production.",
                status_code=403,
            )
        return ActorContext(
            actor_id=self._settings.mcp_dev_actor_id,
            actor_type=ActorType.AI_AGENT,
            roles=(OntologyRole.AI_AGENT,),
            invocation_source=InvocationSource.MCP,
        )


def build_http_identity_resolver(settings: Settings) -> HttpMcpIdentityResolver:
    """Build the remote MCP HTTP identity resolver for the current settings."""
    return HttpMcpIdentityResolver(UnconfiguredRemoteMcpTokenVerifier(settings))


def build_stdio_development_identity_resolver(
    settings: Settings,
) -> StdioDevelopmentIdentityResolver:
    """Build the stdio development identity resolver for the current settings."""
    return StdioDevelopmentIdentityResolver(settings)


def _coerce_ai_agent_actor(
    actor: ActorContext,
    *,
    invocation_source: InvocationSource,
) -> ActorContext:
    """Normalize any verified remote MCP identity to the trusted Version 1 AI shape."""
    return ActorContext(
        actor_id=actor.actor_id,
        actor_type=ActorType.AI_AGENT,
        roles=(OntologyRole.AI_AGENT,),
        invocation_source=invocation_source,
    )
