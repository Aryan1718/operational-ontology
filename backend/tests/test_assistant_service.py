from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence

import pytest
from pydantic import ValidationError

from app.assistant.events import AssistantEvent
from app.assistant.runner import AssistantRunner, OpenAIAssistantRunner
from app.assistant.schemas import MAX_MESSAGE_LENGTH, AssistantChatRequest
from app.assistant.service import AssistantService
from app.core.config import Settings, get_settings
from app.mcp.context import get_current_mcp_actor
from app.mcp.server import create_mcp_server
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)


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


class _SlowRunner(AssistantRunner):
    async def run_stream(self, **_: object) -> AsyncIterator[AssistantEvent]:
        await asyncio.sleep(2)
        yield AssistantEvent(event="message.delta", data={"delta": "late"})


class _StubMcpServer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], ActorContext | None]] = []

    async def call_tool(self, tool_name: str, arguments: dict[str, object]):
        self.calls.append((tool_name, arguments, get_current_mcp_actor()))
        return (
            None,
            {
                "result": {"mitigationPlanId": "PLAN-123"},
                "evidence": [
                    {
                        "objectType": "RiskEvent",
                        "objectId": "RISK-102",
                        "title": "Risk RISK-102",
                        "href": "/objects/RiskEvent/RISK-102",
                    }
                ],
            },
        )


def _settings(**overrides: object) -> Settings:
    get_settings.cache_clear()
    values = get_settings().model_dump(by_alias=True)
    for key, value in overrides.items():
        alias = Settings.model_fields[key].alias or key
        values[alias] = value
    return Settings(**values)


def _human_actor(role: OntologyRole = OntologyRole.PLANNER) -> ActorContext:
    return ActorContext(
        actor_id="planner-001",
        actor_type=ActorType.HUMAN,
        roles=(role,),
        invocation_source=InvocationSource.API,
    )


async def _collect_events(
    service: AssistantService,
    request: AssistantChatRequest,
    *,
    human_actor: ActorContext | None = None,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    async for chunk in service.stream_chat(
        request=request,
        human_actor=human_actor or _human_actor(),
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


def _service(
    runner: AssistantRunner, settings: Settings | None = None
) -> AssistantService:
    resolved_settings = settings or _settings()
    return AssistantService(
        settings=resolved_settings,
        mcp_server=create_mcp_server(resolved_settings),
        runner=runner,
    )


def test_request_schema_accepts_valid_message() -> None:
    request = AssistantChatRequest(
        message="Which orders are impacted by Supplier S-102?",
        contextObject={"objectType": "Supplier", "objectId": "S-102"},
    )

    assert request.message == "Which orders are impacted by Supplier S-102?"
    assert request.context_object is not None
    assert request.context_object.object_type == "Supplier"


@pytest.mark.parametrize("message", ["", "   "])
def test_request_schema_rejects_blank_message(message: str) -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(message=message)


def test_request_schema_rejects_oversized_message() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(message="x" * (MAX_MESSAGE_LENGTH + 1))


def test_request_schema_rejects_excessive_history() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(
            message="hello",
            history=[{"role": "user", "message": "hi"}] * 21,
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("actorId", "admin-001"),
        ("actorType", "human"),
        ("roles", ["Admin"]),
        ("aiActor", {"actorId": "fake-ai"}),
        ("invocationSource", "internal"),
        ("mcpConfig", {"tools": ["approveMitigationPlan"]}),
    ],
)
def test_request_schema_rejects_trusted_or_mcp_fields(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest.model_validate({"message": "hello", field_name: value})


@pytest.mark.parametrize(
    "role",
    [
        OntologyRole.VIEWER,
        OntologyRole.PLANNER,
        OntologyRole.OPERATIONS_MANAGER,
        OntologyRole.ADMIN,
    ],
)
def test_service_always_creates_ai_agent_actor_for_any_human_role(
    role: OntologyRole,
) -> None:
    runner = _CapturingRunner([])

    asyncio.run(
        _collect_events(
            _service(runner),
            AssistantChatRequest(
                message="Which orders are impacted by Supplier S-102?"
            ),
            human_actor=_human_actor(role),
        )
    )

    assert runner.last_run_context is not None
    assert runner.last_run_context.ai_actor.actor_id == "ontology-assistant"
    assert runner.last_run_context.ai_actor.actor_type is ActorType.AI_AGENT
    assert runner.last_run_context.ai_actor.roles == (OntologyRole.AI_AGENT,)
    assert (
        runner.last_run_context.ai_actor.invocation_source
        is InvocationSource.AI_WORKFLOW
    )
    assert role not in runner.last_run_context.ai_actor.roles


def test_service_creates_separate_trusted_ai_actor() -> None:
    runner = _CapturingRunner([])

    asyncio.run(
        _collect_events(
            _service(runner),
            AssistantChatRequest(
                message="Which orders are impacted by Supplier S-102?"
            ),
        )
    )

    assert runner.last_run_context is not None
    assert runner.last_run_context.initiated_by_actor_id == "planner-001"
    assert runner.last_run_context.ai_actor.actor_type is ActorType.AI_AGENT
    assert runner.last_run_context.ai_actor.roles == (OntologyRole.AI_AGENT,)
    assert OntologyRole.PLANNER not in runner.last_run_context.ai_actor.roles
    assert OntologyRole.ADMIN not in runner.last_run_context.ai_actor.roles
    assert (
        runner.last_run_context.ai_actor.invocation_source
        is InvocationSource.AI_WORKFLOW
    )


@pytest.mark.parametrize(
    "message",
    [
        "What should we do?",
        "What is the recommended mitigation?",
        "Show me a mitigation plan.",
        "What would the plan look like?",
        "Can this risk be mitigated?",
    ],
)
def test_service_blocks_draft_tool_without_explicit_current_message_intent(
    message: str,
) -> None:
    runner = _CapturingRunner([])

    asyncio.run(
        _collect_events(
            _service(runner),
            AssistantChatRequest(
                message=message,
                history=[{"role": "user", "message": "Create the mitigation plan."}],
            ),
        )
    )

    assert runner.last_allowed_tool_names is not None
    assert "generateMitigationPlan" not in runner.last_allowed_tool_names
    assert "recommendMitigationPlan" in runner.last_allowed_tool_names


@pytest.mark.parametrize(
    "message",
    [
        "Create a draft mitigation plan.",
        "Generate the mitigation plan.",
        "Save this recommendation as a mitigation plan.",
        "Create the draft mitigation plan for this risk.",
    ],
)
def test_service_allows_draft_tool_only_for_explicit_current_message_intent(
    message: str,
) -> None:
    runner = _CapturingRunner([])

    asyncio.run(
        _collect_events(_service(runner), AssistantChatRequest(message=message))
    )

    assert runner.last_allowed_tool_names is not None
    assert "generateMitigationPlan" in runner.last_allowed_tool_names


def test_service_streams_normalized_events_and_deduplicates_evidence() -> None:
    runner = _CapturingRunner(
        [
            AssistantEvent(
                event="message.delta", data={"delta": "Supplier S-102 impacts "}
            ),
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

    events = asyncio.run(
        _collect_events(
            _service(runner),
            AssistantChatRequest(
                message="Which orders are impacted by Supplier S-102?"
            ),
        )
    )

    assert events[0]["event"] == "run.started"
    assert any(event["event"] == "message.delta" for event in events)
    tool_started = next(event for event in events if event["event"] == "tool.started")
    assert tool_started["data"]["label"] == "Finding impacted orders"
    tool_completed = next(
        event for event in events if event["event"] == "tool.completed"
    )
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

    events = asyncio.run(
        _collect_events(
            _service(runner),
            AssistantChatRequest(message="Approve and execute PLAN-123."),
        )
    )

    assert events[1]["event"] == "message.delta"
    assert "governed human workflow" in events[1]["data"]["delta"]
    assert events[-1]["event"] == "run.completed"
    assert events[-1]["data"]["usage"]["toolCalls"] == 0
    assert runner.last_run_context is None


def test_service_produces_failure_event_from_runner_failure() -> None:
    runner = _CapturingRunner(
        [
            AssistantEvent(
                event="run.failed",
                data={
                    "error": {"code": "ASSISTANT_PROVIDER_ERROR", "message": "failed"}
                },
            )
        ]
    )

    events = asyncio.run(
        _collect_events(_service(runner), AssistantChatRequest(message="hello"))
    )

    assert events[-1]["event"] == "run.failed"
    assert events[-1]["data"]["error"]["code"] == "ASSISTANT_PROVIDER_ERROR"
    assert "requestId" in events[-1]["data"]


def test_service_timeout_produces_safe_failure_event() -> None:
    events = asyncio.run(
        _collect_events(
            _service(_SlowRunner(), settings=_settings(ai_run_timeout_seconds=1)),
            AssistantChatRequest(message="hello"),
        )
    )

    assert events[-1]["event"] == "run.failed"
    assert events[-1]["data"]["error"]["code"] == "ASSISTANT_TIMEOUT"
    assert "traceback" not in json.dumps(events[-1]["data"]).lower()


def test_service_tool_limit_produces_safe_failure_event() -> None:
    runner = _CapturingRunner(
        [
            AssistantEvent(event="tool.started", data={"toolName": "searchObjects"}),
            AssistantEvent(event="tool.started", data={"toolName": "getObject"}),
        ]
    )

    events = asyncio.run(
        _collect_events(
            _service(runner, settings=_settings(ai_max_tool_calls=1)),
            AssistantChatRequest(message="hello"),
        )
    )

    assert events[-1]["event"] == "run.failed"
    assert events[-1]["data"]["error"]["code"] == "ASSISTANT_TOOL_LIMIT_EXCEEDED"


def test_openai_runner_mcp_invoker_uses_local_mcp_actor_and_result_limits() -> None:
    settings = _settings(openai_api_key="test-key", ai_max_result_items=5)
    mcp_server = _StubMcpServer()
    runner = OpenAIAssistantRunner(settings=settings, mcp_server=mcp_server)  # type: ignore[arg-type]
    run_context = _service(_CapturingRunner([]), settings=settings)._build_run_context(
        request=AssistantChatRequest(message="Create a draft mitigation plan."),
        human_actor=_human_actor(OntologyRole.ADMIN),
        request_id="req-123",
    )
    invoker = runner._build_mcp_invoker("searchObjects", run_context)

    output = asyncio.run(invoker(None, json.dumps({"payload": {"limit": 99}})))

    assert mcp_server.calls == [
        (
            "searchObjects",
            {"payload": {"limit": 5}},
            run_context.ai_actor,
        )
    ]
    assert json.loads(output)["evidence"][0]["objectId"] == "RISK-102"
