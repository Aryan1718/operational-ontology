"""Request-scoped trusted MCP actor context."""

from __future__ import annotations

from contextvars import ContextVar, Token

from app.ontology.actor_context import ActorContext

_CURRENT_MCP_ACTOR: ContextVar[ActorContext | None] = ContextVar(
    "current_mcp_actor",
    default=None,
)


def get_current_mcp_actor() -> ActorContext | None:
    """Return the trusted MCP actor bound to the current execution context."""
    return _CURRENT_MCP_ACTOR.get()


def set_current_mcp_actor(actor: ActorContext) -> Token[ActorContext | None]:
    """Bind a trusted MCP actor to the current execution context."""
    return _CURRENT_MCP_ACTOR.set(actor)


def reset_current_mcp_actor(token: Token[ActorContext | None]) -> None:
    """Restore the previous MCP actor binding."""
    _CURRENT_MCP_ACTOR.reset(token)
