"""Assistant chat route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_assistant_service, get_request_actor_context
from app.api.response_contract import get_request_id
from app.assistant.schemas import AssistantChatRequest
from app.assistant.service import AssistantService
from app.ontology.actor_context import ActorContext

router = APIRouter()

AssistantServiceDependency = Annotated[AssistantService, Depends(get_assistant_service)]
ActorContextDependency = Annotated[ActorContext, Depends(get_request_actor_context)]


@router.post("/chat")
async def chat(
    request: Request,
    assistant_request: AssistantChatRequest,
    actor: ActorContextDependency,
    assistant_service: AssistantServiceDependency,
) -> StreamingResponse:
    """Stream normalized assistant events over SSE."""
    return StreamingResponse(
        assistant_service.stream_chat(
            request=assistant_request,
            human_actor=actor,
            request_id=get_request_id(request),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
