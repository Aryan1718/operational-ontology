"""Thin MCP-facing gateway over the existing ontology runtimes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import ObjectTypeNotFoundError
from app.db.session import get_session_factory
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
)
from app.ontology.loader import load_ontology_registry
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository
from app.runtime.authorization_service import AuthorizationService
from app.runtime.function_engine import FunctionEngine
from app.runtime.function_registry import build_function_handler_registry
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.objects import (
    LinkedObjectsResponse,
    ObjectSearchFilter,
    ObjectSearchRequest,
    ObjectSearchSort,
    OntologyObjectResponse,
)


class SearchObjectsToolInput(BaseModel):
    """Typed MCP input for searching one ontology object type."""

    model_config = ConfigDict(extra="ignore")

    objectType: str
    query: str | None = None
    filters: list[ObjectSearchFilter] | None = None
    sort: list[ObjectSearchSort] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None

    def to_search_request(self) -> ObjectSearchRequest:
        """Map MCP input to the existing object search request DTO."""
        return ObjectSearchRequest(
            query=self.query,
            filters=self.filters,
            sort=self.sort,
            limit=self.limit,
            cursor=self.cursor,
        )


class GetObjectToolInput(BaseModel):
    """Typed MCP input for retrieving one ontology object."""

    model_config = ConfigDict(extra="ignore")

    objectType: str
    objectId: str


class GetLinkedObjectsToolInput(BaseModel):
    """Typed MCP input for retrieving objects from one declared ontology link."""

    model_config = ConfigDict(extra="ignore")

    objectType: str
    objectId: str
    linkType: str


class SearchObjectsToolResult(BaseModel):
    """Structured MCP result for object search."""

    objectType: str
    items: list[OntologyObjectResponse]
    nextCursor: str | None = None
    hasMore: bool = False


class GetLinkedObjectsToolResult(BaseModel):
    """Structured MCP result for one link traversal."""

    sourceObjectType: str
    sourceObjectId: str
    linkType: str
    targetObjectType: str
    cardinality: str
    items: list[OntologyObjectResponse]

    @classmethod
    def from_linked_objects_response(
        cls,
        response: LinkedObjectsResponse,
    ) -> GetLinkedObjectsToolResult:
        """Map the existing link runtime response to the MCP result shape."""
        return cls(
            sourceObjectType=response.source.objectType,
            sourceObjectId=response.source.objectId,
            linkType=response.linkType,
            targetObjectType=response.targetObjectType,
            cardinality=response.cardinality,
            items=response.objects,
        )


class FunctionToolResult(BaseModel):
    """Structured MCP result for one ontology function execution."""

    functionName: str
    result: Any
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class OntologyToolGateway:
    """Narrow MCP-facing adapter over the existing ontology runtimes."""

    session_factory: sessionmaker[Session]
    registry_provider: Callable[[], OntologyRegistry]
    authorization_service_provider: Callable[[], AuthorizationService]

    def search_objects(
        self,
        *,
        actor: ActorContext,
        payload: SearchObjectsToolInput,
    ) -> SearchObjectsToolResult:
        """Search one ontology object type through the existing object runtime."""
        self._authorize_object_capability(
            actor=actor,
            capability=AuthorizationCapability.OBJECT_SEARCH,
            object_type=payload.objectType,
        )
        with self.session_factory() as session:
            runtime = self._build_object_runtime(session)
            result = runtime.search_objects(
                object_type=payload.objectType,
                request=payload.to_search_request(),
            )
        return SearchObjectsToolResult(
            objectType=result.response.objectType,
            items=result.response.objects,
            nextCursor=result.next_cursor,
            hasMore=result.has_more,
        )

    def get_object(
        self,
        *,
        actor: ActorContext,
        payload: GetObjectToolInput,
    ) -> OntologyObjectResponse:
        """Retrieve one ontology object through the existing object runtime."""
        self._authorize_object_capability(
            actor=actor,
            capability=AuthorizationCapability.OBJECT_READ,
            object_type=payload.objectType,
        )
        with self.session_factory() as session:
            runtime = self._build_object_runtime(session)
            return runtime.get_object(
                object_type=payload.objectType,
                object_id=payload.objectId,
            )

    def get_linked_objects(
        self,
        *,
        actor: ActorContext,
        payload: GetLinkedObjectsToolInput,
    ) -> GetLinkedObjectsToolResult:
        """Resolve one declared ontology link through the existing link runtime."""
        with self.session_factory() as session:
            runtime = self._build_link_runtime(session)
            response = runtime.get_linked_objects(
                object_type=payload.objectType,
                object_id=payload.objectId,
                link_type=payload.linkType,
                actor=actor,
            )
        return GetLinkedObjectsToolResult.from_linked_objects_response(response)

    def execute_function(
        self,
        *,
        actor: ActorContext,
        function_name: str,
        payload: BaseModel,
    ) -> FunctionToolResult:
        """Execute one existing read-only ontology function through FunctionEngine."""
        with self.session_factory() as session:
            engine = self._build_function_engine(session)
            executed = engine.execute(
                actor=actor,
                function_name=function_name,
                raw_parameters=payload.model_dump(mode="python", by_alias=True),
                request_id="mcp-tool-call",
            )
        return FunctionToolResult.model_validate(
            executed.payload.model_dump(mode="python", by_alias=True)
        )

    def _build_object_runtime(self, session: Session) -> ObjectRuntime:
        registry = self.registry_provider()
        return ObjectRuntime(
            registry=registry,
            repository=ObjectRepository(session),
        )

    def _build_link_runtime(self, session: Session) -> LinkRuntime:
        registry = self.registry_provider()
        repository = ObjectRepository(session)
        object_runtime = ObjectRuntime(
            registry=registry,
            repository=repository,
        )
        return LinkRuntime(
            registry=registry,
            repository=repository,
            object_runtime=object_runtime,
            authorization_service=self.authorization_service_provider(),
        )

    def _build_function_engine(self, session: Session) -> FunctionEngine:
        return FunctionEngine(
            registry=self.registry_provider(),
            authorization_service=self.authorization_service_provider(),
            handler_registry=build_function_handler_registry(),
            session=session,
        )

    def _authorize_object_capability(
        self,
        *,
        actor: ActorContext,
        capability: AuthorizationCapability,
        object_type: str,
    ) -> None:
        if self.registry_provider().get_object_type(object_type) is None:
            raise ObjectTypeNotFoundError(object_type)
        self.authorization_service_provider().authorize_or_raise(
            AuthorizationRequest(
                actor=actor,
                capability=capability,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.OBJECT_TYPE,
                    resource_key=object_type,
                ),
            )
        )


@lru_cache
def _get_default_registry() -> OntologyRegistry:
    """Return the shared default ontology registry for stdio MCP use."""
    return load_ontology_registry()


@lru_cache
def _get_default_authorization_service() -> AuthorizationService:
    """Return the shared default authorization service for stdio MCP use."""
    return AuthorizationService(_get_default_registry().permission_registry)


def build_default_ontology_tool_gateway() -> OntologyToolGateway:
    """Build the default MCP gateway for transports outside FastAPI request DI."""
    return OntologyToolGateway(
        session_factory=get_session_factory(),
        registry_provider=_get_default_registry,
        authorization_service_provider=_get_default_authorization_service,
    )
