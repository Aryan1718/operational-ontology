"""Assistant runner abstractions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.assistant.events import AssistantEvent
from app.assistant.run_context import AssistantRunContext
from app.assistant.schemas import AssistantChatRequest


class AssistantRunner(Protocol):
    async def run_stream(
        self,
        *,
        request: AssistantChatRequest,
        run_context: AssistantRunContext,
        instructions: str,
        allowed_tool_names: Sequence[str],
    ) -> AsyncIterator[AssistantEvent]:
        """Yield normalized assistant events."""


@dataclass(frozen=True)
class UnavailableAssistantRunner:
    async def run_stream(
        self,
        *,
        request: AssistantChatRequest,
        run_context: AssistantRunContext,
        instructions: str,
        allowed_tool_names: Sequence[str],
    ) -> AsyncIterator[AssistantEvent]:
        del request, instructions, allowed_tool_names
        await asyncio.sleep(0)
        yield AssistantEvent(
            event="run.failed",
            data={
                "runId": run_context.run_id,
                "requestId": run_context.request_id,
                "error": {
                    "code": "ASSISTANT_PROVIDER_ERROR",
                    "message": "The assistant provider is not configured.",
                },
            },
        )
