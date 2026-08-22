"""Trusted assistant run context."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ontology.actor_context import ActorContext


class AssistantRunContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(alias="runId")
    conversation_id: str = Field(alias="conversationId")
    initiated_by_actor_id: str = Field(alias="initiatedByActorId")
    ai_actor: ActorContext = Field(alias="aiActor")
    request_id: str = Field(alias="requestId")
    started_at: datetime = Field(alias="startedAt")
