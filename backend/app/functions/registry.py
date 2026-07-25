"""Stable ontology function handler registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class FunctionRegistryError(RuntimeError):
    """Raised when function handler metadata is invalid or incomplete."""


@dataclass(frozen=True, slots=True)
class RegisteredFunctionHandler:
    """One registered executable ontology function."""

    handler_name: str
    input_model: type[BaseModel]
    output_model: Any
    execute: Callable[..., Any]


class FunctionHandlerRegistry:
    """Immutable map of stable ontology handler names to implementations."""

    def __init__(self, handlers: dict[str, RegisteredFunctionHandler]) -> None:
        self._handlers = dict(handlers)

    def get(self, handler_name: str) -> RegisteredFunctionHandler | None:
        """Return one registered function handler by stable name."""
        return self._handlers.get(handler_name)

    def require(self, handler_name: str) -> RegisteredFunctionHandler:
        """Return one registered handler or raise a startup/runtime-safe error."""
        handler = self.get(handler_name)
        if handler is None:
            raise FunctionRegistryError(
                f"Function handler '{handler_name}' is not registered."
            )
        return handler
