"""Stable assistant SSE event models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistantEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str = Field(alias="objectType")
    object_id: str = Field(alias="objectId")
    title: str | None = None
    href: str


class AssistantCreatedObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str = Field(alias="objectType")
    object_id: str = Field(alias="objectId")
    href: str


class AssistantEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal[
        "run.started",
        "message.delta",
        "tool.started",
        "tool.completed",
        "evidence.added",
        "run.completed",
        "run.failed",
    ]
    data: dict[str, Any]
