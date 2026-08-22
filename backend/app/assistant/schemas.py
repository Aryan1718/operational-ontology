"""Assistant request DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_MESSAGE_LENGTH = 4_000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_MESSAGE_LENGTH = 4_000


class AssistantContextObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str = Field(alias="objectType", min_length=1, max_length=120)
    object_id: str = Field(alias="objectId", min_length=1, max_length=120)

    @field_validator("object_type", "object_id")
    @classmethod
    def _reject_blank_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank.")
        return normalized


class AssistantHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "tool"]
    message: str = Field(min_length=1, max_length=MAX_HISTORY_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def _reject_blank_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("History message must not be blank.")
        return normalized


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(default=None, alias="conversationId", max_length=120)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: list[AssistantHistoryMessage] = Field(default_factory=list)
    context_object: AssistantContextObject | None = Field(default=None, alias="contextObject")

    @field_validator("conversation_id")
    @classmethod
    def _normalize_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message must not be blank.")
        return normalized

    @model_validator(mode="after")
    def _validate_history_limit(self) -> "AssistantChatRequest":
        if len(self.history) > MAX_HISTORY_MESSAGES:
            raise ValueError(
                f"History may contain at most {MAX_HISTORY_MESSAGES} messages."
            )
        return self
