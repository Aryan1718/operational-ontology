"""Assistant runner abstractions and OpenAI Agents SDK integration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from app.assistant.events import AssistantEvent
from app.assistant.run_context import AssistantRunContext
from app.assistant.schemas import AssistantChatRequest
from app.core.config import Settings
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor


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


@dataclass(frozen=True)
class OpenAIAssistantRunner:
    """Run the in-app assistant with OpenAI Agents SDK over local MCP tools."""

    settings: Settings
    mcp_server: FastMCP

    async def run_stream(
        self,
        *,
        request: AssistantChatRequest,
        run_context: AssistantRunContext,
        instructions: str,
        allowed_tool_names: Sequence[str],
    ) -> AsyncIterator[AssistantEvent]:
        if not self.settings.openai_api_key:
            async for event in UnavailableAssistantRunner().run_stream(
                request=request,
                run_context=run_context,
                instructions=instructions,
                allowed_tool_names=allowed_tool_names,
            ):
                yield event
            return

        try:
            from agents import (
                Agent,
                FunctionTool,
                RunConfig,
                Runner,
                set_default_openai_key,
            )
            from agents.tracing import set_tracing_disabled
        except ImportError:
            async for event in UnavailableAssistantRunner().run_stream(
                request=request,
                run_context=run_context,
                instructions=instructions,
                allowed_tool_names=allowed_tool_names,
            ):
                yield event
            return

        set_default_openai_key(self.settings.openai_api_key, use_for_tracing=False)
        set_tracing_disabled(not self.settings.ai_tracing_enabled)
        tools = await self._build_mcp_tools(
            function_tool_type=FunctionTool,
            run_context=run_context,
            allowed_tool_names=allowed_tool_names,
        )
        agent = Agent(
            name="Ontology Assistant",
            instructions=instructions,
            model=self.settings.ai_model,
            tools=tools,
        )
        run_config = RunConfig(
            tracing_disabled=not self.settings.ai_tracing_enabled,
            trace_include_sensitive_data=False,
            workflow_name="in_app_assistant",
            group_id=run_context.conversation_id,
            trace_metadata={
                "runId": run_context.run_id,
                "requestId": run_context.request_id,
            },
        )
        result = Runner.run_streamed(
            agent,
            input=self._build_input(request),
            context=run_context,
            max_turns=self.settings.ai_max_tool_calls + 2,
            run_config=run_config,
        )
        try:
            async for stream_event in result.stream_events():
                async for event in self._map_stream_event(stream_event):
                    yield event
        except asyncio.CancelledError:
            cancel = getattr(result, "cancel", None)
            if callable(cancel):
                cancel()
            raise

    async def _build_mcp_tools(
        self,
        *,
        function_tool_type: type[Any],
        run_context: AssistantRunContext,
        allowed_tool_names: Sequence[str],
    ) -> list[Any]:
        allowed = set(allowed_tool_names)
        tools = []
        for mcp_tool in await self.mcp_server.list_tools():
            if mcp_tool.name not in allowed:
                continue
            tools.append(
                function_tool_type(
                    name=mcp_tool.name,
                    description=mcp_tool.description or mcp_tool.name,
                    params_json_schema=mcp_tool.inputSchema,
                    on_invoke_tool=self._build_mcp_invoker(mcp_tool.name, run_context),
                )
            )
        return tools

    def _build_mcp_invoker(self, tool_name: str, run_context: AssistantRunContext):
        async def _invoke_tool(_context: Any, arguments: str) -> str:
            parsed_arguments = self._apply_tool_limits(json.loads(arguments))
            token = set_current_mcp_actor(run_context.ai_actor)
            try:
                result = await self.mcp_server.call_tool(tool_name, parsed_arguments)
            finally:
                reset_current_mcp_actor(token)
            return json.dumps(self._safe_json(result), separators=(",", ":"))

        return _invoke_tool

    def _apply_tool_limits(self, arguments: object) -> object:
        if not isinstance(arguments, dict):
            return arguments
        payload = arguments.get("payload")
        if isinstance(payload, dict):
            limit = payload.get("limit")
            if isinstance(limit, int):
                payload["limit"] = min(limit, self.settings.ai_max_result_items)
        return arguments

    def _build_input(self, request: AssistantChatRequest) -> list[dict[str, str]]:
        input_items: list[dict[str, str]] = []
        for history_message in request.history[
            -self.settings.ai_max_history_messages :
        ]:
            if history_message.role == "tool":
                continue
            input_items.append(
                {
                    "role": history_message.role,
                    "content": history_message.message,
                }
            )
        message = request.message
        if request.context_object is not None:
            message = (
                f"{message}\n\nCurrent context object: "
                f"{request.context_object.object_type} "
                f"{request.context_object.object_id}"
            )
        input_items.append({"role": "user", "content": message})
        return input_items

    async def _map_stream_event(
        self,
        stream_event: object,
    ) -> AsyncIterator[AssistantEvent]:
        event_type = getattr(stream_event, "type", None)
        if event_type == "raw_response_event":
            delta = self._extract_text_delta(getattr(stream_event, "data", None))
            if delta:
                yield AssistantEvent(event="message.delta", data={"delta": delta})
            return

        if event_type != "run_item_stream_event":
            return
        name = getattr(stream_event, "name", None)
        item = getattr(stream_event, "item", None)
        item_type = getattr(item, "type", None)
        if name == "tool_called" or item_type == "tool_call_item":
            yield AssistantEvent(
                event="tool.started",
                data={
                    "toolName": self._extract_first_attr(item, ("name", "tool_name")),
                    "toolCallId": self._extract_first_attr(
                        item,
                        ("id", "call_id", "tool_call_id"),
                    ),
                },
            )
            return
        if name == "tool_output" or item_type == "tool_call_output_item":
            output = self._extract_first_attr(item, ("output", "raw_item"))
            data = {
                "toolName": self._extract_first_attr(item, ("name", "tool_name")),
                "toolCallId": self._extract_first_attr(
                    item,
                    ("id", "call_id", "tool_call_id"),
                ),
            }
            result_data = self._parse_json_output(output)
            created_object = self._extract_created_object(result_data)
            if created_object:
                data["createdObject"] = created_object
            yield AssistantEvent(event="tool.completed", data=data)
            for evidence in self._extract_evidence(result_data):
                yield AssistantEvent(
                    event="evidence.added", data={"evidence": evidence}
                )

    def _extract_text_delta(self, data: object) -> str | None:
        event_name = getattr(data, "type", "")
        if event_name not in {"response.output_text.delta", "response.text.delta"}:
            return None
        delta = getattr(data, "delta", None)
        return delta if isinstance(delta, str) else None

    def _extract_first_attr(self, item: object, names: Sequence[str]) -> str:
        for name in names:
            value = getattr(item, name, None)
            if isinstance(value, str):
                return value
            nested = getattr(item, "raw_item", None)
            nested_value = getattr(nested, name, None)
            if isinstance(nested_value, str):
                return nested_value
        return ""

    def _parse_json_output(self, output: object) -> object:
        if isinstance(output, str):
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return None
        return self._safe_json(output)

    def _extract_evidence(self, result_data: object) -> list[dict[str, str]]:
        if not isinstance(result_data, dict):
            return []
        evidence = result_data.get("evidence")
        if not isinstance(evidence, list):
            return []
        safe_items: list[dict[str, str]] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            object_type = item.get("objectType")
            object_id = item.get("objectId")
            if not isinstance(object_type, str) or not isinstance(object_id, str):
                continue
            title = item.get("title")
            href = item.get("href")
            safe_items.append(
                {
                    "objectType": object_type,
                    "objectId": object_id,
                    "title": title
                    if isinstance(title, str)
                    else f"{object_type} {object_id}",
                    "href": href
                    if isinstance(href, str)
                    else f"/objects/{object_type}/{object_id}",
                }
            )
        return safe_items[: self.settings.ai_max_result_items]

    def _extract_created_object(self, result_data: object) -> dict[str, str] | None:
        if not isinstance(result_data, dict):
            return None
        result = result_data.get("result")
        if not isinstance(result, dict):
            return None
        plan_id = result.get("mitigationPlanId")
        if not isinstance(plan_id, str):
            return None
        return {
            "objectType": "MitigationPlan",
            "objectId": plan_id,
            "href": f"/objects/MitigationPlan/{plan_id}",
        }

    def _safe_json(self, value: object) -> object:
        if isinstance(value, BaseException):
            return {"error": value.__class__.__name__}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True)
        if isinstance(value, tuple):
            if len(value) == 2 and isinstance(value[1], dict):
                return self._safe_json(value[1])
            return [self._safe_json(item) for item in value]
        if isinstance(value, list):
            return [self._safe_json(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._safe_json(item)
                for key, item in value.items()
                if str(key) not in {"actor", "authorization", "credentials", "token"}
            }
        return value
