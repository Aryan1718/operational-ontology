"""Stable ontology action handler registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class ActionRegistryError(KeyError):
    """Raised when a stable action handler name is missing."""


@dataclass(frozen=True, slots=True)
class RegisteredActionHandler:
    """Immutable action handler registration."""

    handler_name: str
    input_model: type[BaseModel]
    output_model: Any
    execute: Any


class ActionHandlerRegistry:
    """Immutable lookup of stable ontology action handlers."""

    def __init__(self, handlers: Mapping[str, RegisteredActionHandler]) -> None:
        self._handlers = dict(handlers)

    def require(self, handler_name: str) -> RegisteredActionHandler:
        handler = self._handlers.get(handler_name)
        if handler is None:
            raise ActionRegistryError(handler_name)
        return handler
