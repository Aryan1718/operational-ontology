from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence

from app.assistant.events import AssistantEvent
from app.assistant.runner import AssistantRunner
from app.assistant.schemas import AssistantChatRequest
from app.assistant.service import AssistantService
from app.core.config import Settings, get_settings
from app.mcp.server import create_mcp_server
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole


class _CapturingRunner(AssistantRunner):
    def __init__(self, events: Sequence[AssistantEvent]) -> None:
        self._events = list(events)
        self.last_run_context = None
        self.last_allowed_tool_names: Sequence[str] | None = None

    async def run_stream(
        self,
        *,
        request: AssistantChatRequest,
        run_context,
        instructions: str,
        allowed_tool_names: Sequence[str],
    ) -> AsyncIterator[AssistantEvent]:
        del request, instructions
        self.last_run_context = run_context
        self.last_allowed_tool_names = allowed_tool_names
        for event in self._events:
            yield event


def _settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def _human_actor(role: OntologyRole = OntologyRole.PLANNER) -> ActorContext:
    return ActorContext(
        actor_id="planner-001",
        actor_type=ActorType.HUMAN,
        roles=(role,),
        invocation_source=InvocationSource.API,
    )


async def _collect_events(service: AssistantService, request: AssistantChatRequest) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    async for chunk in service.stream_chat(
        request=request,
        human_actor=_human_actor(),
        request_id="req-123",
    ):
        event_line, data_line = chunk.strip().splitlines()
        events.append(
            {
                "event": event_line.removeprefix("event: "),
                "data": json.loads(data_line.removeprefix("data: ")),
            }
        )
    return events


def test_service_creates_separate_trusted_ai_actor() -> None:
    runner = _CapturingRunner([])
    service = AssistantService(
        settings=_settings(),
        mcp_server=create_mcp_server(_settings()),
        runner=runner,
    )

    asyncio.run(
        _collect_events(
            service,
            AssistantChatRequest(message="Which orders are impacted by Supplier S-102?"),
        )
    )

    assert runner.last_run_context is not None
    assert runner.last_run_context.initiated_by_actor_id == "planner-001"
    assert runner.last_run_context.ai_actor.actor_type is ActorType.AI_AGENT
    assert runner.last_run_context.ai_actor.roles == (OntologyRole.AI_AGENT,)
    assert OntologyRole.PLANNER not in runner.last_run_context.ai_actor.roles
    assert OntologyRole.ADMIN not in runner.last_run_context.ai_actor.roles
    assert runner.last_run_context.ai_actor.invocation_source is InvocationSource.AI_WORKFLOW


def test_service_blocks_generate_mitigation_plan_without_explicit_current_message_intent() -> None:
    runner = _CapturingRunner([])
    service = AssistantService(
        settings=_settings(),
        mcp_server=create_mcp_server(_settings()),
        runner=runner,
    )

    asyncio.run(
        _collect_events(
            service,
            AssistantChatRequest(
                message="What should we do?",
                history=[{"role": "user", "message": "Create the mitigation plan."}],
            ),
        )
    )

    assert runner.last_allowed_tool_names is not None
    assert "generateMitigationPlan" not in runner.last_allowed_tool_names


def test_service_allows_generate_mitigation_plan_only_for_explicit_current_message_intent() -> None:
    runner = _CapturingRunner([])
    service = AssistantService(
        settings=_settings(),
        mcp_server=create_mcp_server(_settings()),
        runner=runner,
    )

    asyncio.run(
        _collect_events(
            service,
            AssistantChatRequest(message="Create the draft mitigation plan for RISK-102."),
        )
    )

    assert runner.last_allowed_tool_names is not None
    assert "generateMitigationPlan" in runner.last_allowed_tool_names


def test_service_streams_normalized_events_and_deduplicates_evidence() -> None:
    runner = _CapturingRunner(
        [
            AssistantEvent(event="message.delta", data={"delta": "Supplier S-102 impacts "}),
            AssistantEvent(
                event="tool.started",
                data={"toolName": "findImpactedOrders", "toolCallId": "tool-1"},
            ),
            AssistantEvent(
                event="evidence.added",
                data={
                    "evidence": {
                        "objectType": "CustomerOrder",
                        "objectId": "ORD-881",
                        "title": "Customer Order ORD-881",
                        "href": "/objects/CustomerOrder/ORD-881",
                    }
                },
            ),
            AssistantEvent(
                event="evidence.added",
                data={
                    "evidence": {
                        "objectType": "CustomerOrder",
                        "objectId": "ORD-881",
                        "title": "Customer Order ORD-881",
                        "href": "/objects/CustomerOrder/ORD-881",
                    }
                },
            ),
            AssistantEvent(
                event="tool.completed",
                data={"toolName": "findImpactedOrders", "toolCallId": "tool-1"},
            ),
            AssistantEvent(event="message.delta", data={"delta": "ORD-881."}),
        ]
    )
    service = AssistantService(
        settings=_settings(),
        mcp_server=create_mcp_server(_settings()),
        runner=runner,
    )

    events = asyncio.run(
        _collect_events(
            service,
            AssistantChatRequest(message="Which orders are impacted by Supplier S-102?"),
        )
    )

    assert events[0]["event"] == "run.started"
    assert any(event["event"] == "message.delta" for event in events)
    tool_started = next(event for event in events if event["event"] == "tool.started")
    assert tool_started["data"]["label"] == "Finding impacted orders"
    tool_completed = next(event for event in events if event["event"] == "tool.completed")
    assert tool_completed["data"]["status"] == "completed"
    completed = events[-1]
    assert completed["event"] == "run.completed"
    assert completed["data"]["message"] == "Supplier S-102 impacts ORD-881."
    assert completed["data"]["usage"]["toolCalls"] == 1
    assert completed["data"]["evidence"] == [
        {
            "objectType": "CustomerOrder",
            "objectId": "ORD-881",
            "title": "Customer Order ORD-881",
            "href": "/objects/CustomerOrder/ORD-881",
        }
    ]


def test_service_produces_human_workflow_message_for_human_only_requests() -> None:
    runner = _CapturingRunner([])
    service = AssistantService(
        settings=_settings(),
        mcp_server=create_mcp_server(_settings()),
        runner=runner,
    )

    events = asyncio.run(
        _collect_events(
            service,
            AssistantChatRequest(message="Approve and execute PLAN-123."),
        )
    )

    assert events[1]["event"] == "message.delta"
    assert "governed human workflow" in events[1]["data"]["delta"]
    assert events[-1]["event"] == "run.completed"
    assert events[-1]["data"]["usage"]["toolCalls"] == 0

