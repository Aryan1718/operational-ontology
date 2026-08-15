"""Thin MCP adapter over the shared ontology object and link runtimes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ApplicationError
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository
from app.runtime.authorization_service import AuthorizationService
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.objects import (
    AggregateLinkedObjectsResponse,
    LinkedObjectsResponse,
    ObjectSearchResponse,
    OntologyObjectResponse,
)

from app.mcp.schemas import (
    GetLinkedObjectsInput,
    GetObjectInput,
    McpEvidenceObject,
    McpToolErrorPayload,
    McpToolMeta,
    McpToolResult,
    SearchObjectsInput,
)


class McpToolExecutionError(RuntimeError):
    """Safe MCP tool failure with a structured payload."""

    def __init__(self, payload: McpToolErrorPayload) -> None:
        self.payload = payload
        super().__init__(payload.model_dump_json(by_alias=True))


class OntologyMcpToolAdapter:
    """Invoke the shared ontology read runtimes for MCP tools."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        authorization_service: AuthorizationService,
        session_factory: sessionmaker,
    ) -> None:
        self._registry = registry
        self._authorization_service = authorization_service
        self._session_factory = session_factory

    def search_objects(self, tool_input: SearchObjectsInput | dict[str, object]) -> dict[str, object]:
        request_id = self._new_request_id()
        validated_input = SearchObjectsInput.model_validate(tool_input)
        try:
            with self._session_factory() as session:
                runtime = ObjectRuntime(
                    registry=self._registry,
                    repository=ObjectRepository(session),
                )
                result = runtime.search_objects(
                    object_type=validated_input.objectType,
                    request=validated_input,
                )
                return self._build_result(
                    tool_name="searchObjects",
                    request_id=request_id,
                    data=result.response,
                    evidence=self._evidence_from_search(result.response),
                    next_cursor=result.next_cursor,
                    has_more=result.has_more,
                )
        except ApplicationError as exc:
            self._raise_tool_error("searchObjects", request_id, exc)

    def get_object(self, tool_input: GetObjectInput | dict[str, object]) -> dict[str, object]:
        request_id = self._new_request_id()
        validated_input = GetObjectInput.model_validate(tool_input)
        try:
            with self._session_factory() as session:
                runtime = ObjectRuntime(
                    registry=self._registry,
                    repository=ObjectRepository(session),
                )
                response = runtime.get_object(
                    object_type=validated_input.objectType,
                    object_id=validated_input.objectId,
                )
                return self._build_result(
                    tool_name="getObject",
                    request_id=request_id,
                    data=response,
                    evidence=self._evidence_from_object(response),
                )
        except ApplicationError as exc:
            self._raise_tool_error("getObject", request_id, exc)

    def get_linked_objects(
        self,
        tool_input: GetLinkedObjectsInput | dict[str, object],
    ) -> dict[str, object]:
        request_id = self._new_request_id()
        validated_input = GetLinkedObjectsInput.model_validate(tool_input)
        actor = self._build_actor_context()
        try:
            with self._session_factory() as session:
                repository = ObjectRepository(session)
                object_runtime = ObjectRuntime(
                    registry=self._registry,
                    repository=repository,
                )
                runtime = LinkRuntime(
                    registry=self._registry,
                    repository=repository,
                    object_runtime=object_runtime,
                    authorization_service=self._authorization_service,
                )
                if validated_input.linkType:
                    response = runtime.get_linked_objects(
                        object_type=validated_input.objectType,
                        object_id=validated_input.objectId,
                        link_type=validated_input.linkType,
                        actor=actor,
                    )
                else:
                    response = runtime.get_all_links(
                        object_type=validated_input.objectType,
                        object_id=validated_input.objectId,
                        actor=actor,
                    )
                return self._build_result(
                    tool_name="getLinkedObjects",
                    request_id=request_id,
                    data=response,
                    evidence=self._evidence_from_link_response(response),
                )
        except ApplicationError as exc:
            self._raise_tool_error("getLinkedObjects", request_id, exc)

    def _build_actor_context(self) -> ActorContext:
        return ActorContext(
            actor_id="ontology-assistant",
            actor_type=ActorType.AI_AGENT,
            roles=(OntologyRole.AI_AGENT,),
            invocation_source=InvocationSource.MCP,
        )

    def _build_result(
        self,
        *,
        tool_name: str,
        request_id: str,
        data: ObjectSearchResponse | OntologyObjectResponse | LinkedObjectsResponse | AggregateLinkedObjectsResponse,
        evidence: list[McpEvidenceObject],
        next_cursor: str | None = None,
        has_more: bool | None = None,
    ) -> dict[str, object]:
        result = McpToolResult(
            data=data,
            evidence=evidence,
            warnings=[],
            meta=McpToolMeta(
                toolName=tool_name,
                requestId=request_id,
                ontologyVersion=self._registry.ontology.version,
                permissionPolicyVersion=self._registry.permission_registry.version,
                executedAt=self._now_isoformat(),
                nextCursor=next_cursor,
                hasMore=has_more,
            ),
        )
        return result.model_dump(mode="json", by_alias=True)

    def _raise_tool_error(self, tool_name: str, request_id: str, exc: ApplicationError) -> None:
        raise McpToolExecutionError(
            McpToolErrorPayload(
                code=exc.code,
                message=exc.message,
                retryable=exc.status_code >= 500,
                details=exc.details,
                toolName=tool_name,
                requestId=request_id,
            )
        ) from exc

    def _evidence_from_search(self, response: ObjectSearchResponse) -> list[McpEvidenceObject]:
        return [self._to_evidence_item(object_response) for object_response in response.objects]

    def _evidence_from_object(self, response: OntologyObjectResponse) -> list[McpEvidenceObject]:
        return [self._to_evidence_item(response)]

    def _evidence_from_link_response(
        self,
        response: LinkedObjectsResponse | AggregateLinkedObjectsResponse,
    ) -> list[McpEvidenceObject]:
        evidence_by_key: dict[tuple[str, str], McpEvidenceObject] = {}

        if isinstance(response, LinkedObjectsResponse):
            for object_response in response.objects:
                evidence = self._to_evidence_item(object_response)
                evidence_by_key[(evidence.objectType, evidence.objectId)] = evidence
            return list(evidence_by_key.values())

        for link_response in response.links:
            for object_response in link_response.objects:
                evidence = self._to_evidence_item(object_response)
                evidence_by_key[(evidence.objectType, evidence.objectId)] = evidence
        return list(evidence_by_key.values())

    def _to_evidence_item(self, response: OntologyObjectResponse) -> McpEvidenceObject:
        return McpEvidenceObject(
            objectType=response.objectType,
            objectId=response.objectId,
            title=response.displayName,
            href=f"/objects/{response.objectType}/{response.objectId}",
        )

    @staticmethod
    def _new_request_id() -> str:
        return str(uuid4())

    @staticmethod
    def _now_isoformat() -> str:
        return datetime.now(UTC).isoformat()


def format_tool_error(exc: McpToolExecutionError) -> str:
    """Return the safe structured error string surfaced to MCP clients."""

    return json.dumps({"error": exc.payload.model_dump(mode="json", by_alias=True)})
