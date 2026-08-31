"""Assistant orchestration service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from app.assistant.events import (
    AssistantCreatedObject,
    AssistantEvent,
    AssistantEvidence,
)
from app.assistant.instructions import build_system_instructions
from app.assistant.intent import allows_draft_plan_creation, requests_human_only_action
from app.assistant.run_context import AssistantRunContext
from app.assistant.runner import AssistantRunner
from app.assistant.schemas import AssistantChatRequest
from app.core.config import Settings
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)

_HUMAN_ONLY_MESSAGE = "This operation requires the governed human workflow."
_TOOL_LABELS = {
    "searchObjects": "Searching ontology objects",
    "getObject": "Loading object details",
    "getLinkedObjects": "Inspecting relationships",
    "findImpactedParts": "Finding impacted parts",
    "findImpactedProducts": "Finding impacted products",
    "findImpactedOrders": "Finding impacted orders",
    "calculateStockoutRisk": "Calculating stockout risk",
    "getInventoryAvailability": "Checking inventory availability",
    "findAlternativeWarehouses": "Checking alternative warehouses",
    "findExpeditablePurchaseOrders": "Checking expeditable purchase orders",
    "rankImpactedOrders": "Ranking impacted orders",
    "recommendMitigationPlan": "Evaluating mitigation options",
    "generateMitigationPlan": "Creating draft mitigation plan",
}


@dataclass(frozen=True)
class AssistantService:
    settings: Settings
    mcp_server: FastMCP
    runner: AssistantRunner

    async def stream_chat(
        self,
        *,
        request: AssistantChatRequest,
        human_actor: ActorContext,
        request_id: str,
    ) -> AsyncIterator[str]:
        run_context = self._build_run_context(
            request=request,
            human_actor=human_actor,
            request_id=request_id,
        )
        allowed_tool_names = await self._resolve_allowed_tool_names(request.message)
        yield self._encode_sse(
            AssistantEvent(
                event="run.started",
                data={
                    "runId": run_context.run_id,
                    "conversationId": run_context.conversation_id,
                    "requestId": run_context.request_id,
                },
            )
        )

        if requests_human_only_action(request.message):
            yield self._encode_sse(
                AssistantEvent(
                    event="message.delta",
                    data={"runId": run_context.run_id, "delta": _HUMAN_ONLY_MESSAGE},
                )
            )
            yield self._encode_sse(
                AssistantEvent(
                    event="run.completed",
                    data={
                        "runId": run_context.run_id,
                        "conversationId": run_context.conversation_id,
                        "requestId": run_context.request_id,
                        "message": _HUMAN_ONLY_MESSAGE,
                        "evidence": self._context_evidence(request),
                        "createdObjects": [],
                        "usage": {"toolCalls": 0},
                    },
                )
            )
            return

        message_parts: list[str] = []
        evidence_by_key: dict[tuple[str, str], AssistantEvidence] = {}
        created_objects_by_key: dict[tuple[str, str], AssistantCreatedObject] = {}
        tool_calls = 0

        try:
            async with asyncio.timeout(self.settings.ai_run_timeout_seconds):
                async for raw_event in self.runner.run_stream(
                    request=request,
                    run_context=run_context,
                    instructions=build_system_instructions(),
                    allowed_tool_names=allowed_tool_names,
                ):
                    event = self._normalize_event(raw_event, run_context)
                    if event.event == "message.delta":
                        message_parts.append(str(event.data.get("delta", "")))
                    elif event.event == "tool.started":
                        tool_calls += 1
                        if tool_calls > self.settings.ai_max_tool_calls:
                            yield self._encode_sse(
                                self._failed_event(
                                    run_context,
                                    "ASSISTANT_TOOL_LIMIT_EXCEEDED",
                                )
                            )
                            return
                    elif event.event == "evidence.added" and "evidence" in event.data:
                        evidence = AssistantEvidence.model_validate(
                            event.data["evidence"]
                        )
                        evidence_by_key[(evidence.object_type, evidence.object_id)] = (
                            evidence
                        )
                    elif (
                        event.event == "tool.completed"
                        and "createdObject" in event.data
                    ):
                        created_object = AssistantCreatedObject.model_validate(
                            event.data["createdObject"]
                        )
                        created_objects_by_key[
                            (created_object.object_type, created_object.object_id)
                        ] = created_object
                    elif event.event == "run.failed":
                        yield self._encode_sse(event)
                        return
                    yield self._encode_sse(event)
        except TimeoutError:
            yield self._encode_sse(self._failed_event(run_context, "ASSISTANT_TIMEOUT"))
            return
        except Exception:
            yield self._encode_sse(
                self._failed_event(run_context, "ASSISTANT_RUN_FAILED")
            )
            return

        yield self._encode_sse(
            AssistantEvent(
                event="run.completed",
                data={
                    "runId": run_context.run_id,
                    "conversationId": run_context.conversation_id,
                    "requestId": run_context.request_id,
                    "message": "".join(message_parts),
                    "evidence": [
                        item.model_dump(mode="json", by_alias=True)
                        for item in evidence_by_key.values()
                    ],
                    "createdObjects": [
                        item.model_dump(mode="json", by_alias=True)
                        for item in created_objects_by_key.values()
                    ],
                    "usage": {"toolCalls": tool_calls},
                },
            )
        )

    def _build_run_context(
        self,
        *,
        request: AssistantChatRequest,
        human_actor: ActorContext,
        request_id: str,
    ) -> AssistantRunContext:
        return AssistantRunContext(
            runId=f"run_{uuid4().hex}",
            conversationId=request.conversation_id or f"conv_{uuid4().hex}",
            initiatedByActorId=human_actor.actor_id,
            aiActor=ActorContext(
                actor_id="ontology-assistant",
                actor_type=ActorType.AI_AGENT,
                roles=(OntologyRole.AI_AGENT,),
                invocation_source=InvocationSource.AI_WORKFLOW,
            ),
            requestId=request_id,
            startedAt=datetime.now(UTC),
        )

    async def _resolve_allowed_tool_names(self, current_message: str) -> Sequence[str]:
        tools = await self.mcp_server.list_tools()
        tool_names = [tool.name for tool in tools]
        if allows_draft_plan_creation(current_message):
            return tool_names
        return [
            tool_name
            for tool_name in tool_names
            if tool_name != "generateMitigationPlan"
        ]

    def _normalize_event(
        self,
        event: AssistantEvent,
        run_context: AssistantRunContext,
    ) -> AssistantEvent:
        data = dict(event.data)
        data.setdefault("runId", run_context.run_id)
        data.setdefault("requestId", run_context.request_id)
        if event.event == "tool.started":
            tool_name = str(data.get("toolName", ""))
            data.setdefault("toolCallId", f"tool_{uuid4().hex}")
            data["label"] = _TOOL_LABELS.get(tool_name, "Using ontology tool")
        if event.event == "tool.completed":
            data.setdefault("status", "completed")
        return AssistantEvent(event=event.event, data=data)

    def _failed_event(
        self, run_context: AssistantRunContext, code: str
    ) -> AssistantEvent:
        message = "The assistant could not complete the request."
        if code == "ASSISTANT_TIMEOUT":
            message = "The assistant timed out before completing the request."
        elif code == "ASSISTANT_TOOL_LIMIT_EXCEEDED":
            message = (
                "The assistant reached the configured tool-call limit before "
                "completing the request."
            )
        return AssistantEvent(
            event="run.failed",
            data={
                "runId": run_context.run_id,
                "conversationId": run_context.conversation_id,
                "requestId": run_context.request_id,
                "error": {"code": code, "message": message},
            },
        )

    def _context_evidence(self, request: AssistantChatRequest) -> list[dict[str, str]]:
        if request.context_object is None:
            return []
        return [
            AssistantEvidence(
                objectType=request.context_object.object_type,
                objectId=request.context_object.object_id,
                title=(
                    f"{request.context_object.object_type} "
                    f"{request.context_object.object_id}"
                ),
                href=(
                    f"/objects/{request.context_object.object_type}/"
                    f"{request.context_object.object_id}"
                ),
            ).model_dump(mode="json", by_alias=True)
        ]

    def _encode_sse(self, event: AssistantEvent) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
