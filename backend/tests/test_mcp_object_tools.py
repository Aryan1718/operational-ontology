"""Phase 2 MCP object-tool gateway and registration tests."""

import asyncio
from contextlib import nullcontext

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationDeniedError, LinkNotFoundError, ObjectNotFoundError, ObjectTypeNotFoundError
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor
from app.mcp.ontology_tool_gateway import (
    GetLinkedObjectsToolInput,
    GetObjectToolInput,
    OntologyToolGateway,
    SearchObjectsToolInput,
)
from app.mcp.server import create_mcp_server
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole
from app.ontology.loader import load_ontology_registry
from app.runtime.authorization_service import AuthorizationService
from app.runtime.object_runtime import ObjectSearchResult
from app.schemas.objects import LinkedObjectsResponse, ObjectSearchResponse, OntologyObjectReference, OntologyObjectResponse


def _build_ai_actor() -> ActorContext:
    return ActorContext(
        actor_id="ontology-assistant",
        actor_type=ActorType.AI_AGENT,
        roles=(OntologyRole.AI_AGENT,),
        invocation_source=InvocationSource.MCP,
    )


def _build_unprivileged_ai_actor() -> ActorContext:
    return ActorContext(
        actor_id="untrusted-ai",
        actor_type=ActorType.AI_AGENT,
        roles=(),
        invocation_source=InvocationSource.MCP,
    )


def _supplier_objects() -> list[OntologyObjectResponse]:
    return [
        OntologyObjectResponse(
            objectType="Supplier",
            objectId="S-101",
            displayName="Northstar Components",
            properties={"supplierCode": "S-101", "name": "Northstar Components"},
        ),
        OntologyObjectResponse(
            objectType="Supplier",
            objectId="S-102",
            displayName="Vertex Electronics",
            properties={"supplierCode": "S-102", "name": "Vertex Electronics"},
        ),
        OntologyObjectResponse(
            objectType="Supplier",
            objectId="S-103",
            displayName="Summit Industrial",
            properties={"supplierCode": "S-103", "name": "Summit Industrial"},
        ),
    ]


def _purchase_order_objects() -> list[OntologyObjectResponse]:
    return [
        OntologyObjectResponse(
            objectType="PurchaseOrder",
            objectId=order_id,
            displayName=order_id,
            properties={"purchaseOrderCode": order_id},
        )
        for order_id in ["PO-200", "PO-201", "PO-202", "PO-203", "PO-204"]
    ]


class _StubObjectRuntime:
    def get_object(self, object_type: str, object_id: str) -> OntologyObjectResponse:
        if object_type != "Supplier":
            raise ObjectTypeNotFoundError(object_type)
        for item in _supplier_objects():
            if item.objectId == object_id:
                return item
        raise ObjectNotFoundError(object_type, object_id)

    def search_objects(
        self,
        object_type: str,
        request,
    ) -> ObjectSearchResult:
        del request
        if object_type != "Supplier":
            raise ObjectTypeNotFoundError(object_type)
        return ObjectSearchResult(
            response=ObjectSearchResponse(
                objectType="Supplier",
                objects=_supplier_objects(),
            ),
            next_cursor=None,
            has_more=False,
        )


class _StubLinkRuntime:
    def get_linked_objects(
        self,
        object_type: str,
        object_id: str,
        link_type: str,
        actor: ActorContext,
    ) -> LinkedObjectsResponse:
        del actor
        if object_type != "Supplier":
            raise ObjectTypeNotFoundError(object_type)
        if object_id != "S-102":
            raise ObjectNotFoundError(object_type, object_id)
        if link_type != "supplierToPurchaseOrders":
            raise LinkNotFoundError(object_type, link_type)
        return LinkedObjectsResponse(
            source=OntologyObjectReference(objectType="Supplier", objectId="S-102"),
            linkType="supplierToPurchaseOrders",
            targetObjectType="PurchaseOrder",
            cardinality="one-to-many",
            objects=_purchase_order_objects(),
        )


class _StubGateway(OntologyToolGateway):
    def _build_object_runtime(self, session):
        del session
        return _StubObjectRuntime()

    def _build_link_runtime(self, session):
        del session
        return _StubLinkRuntime()


def _build_gateway() -> OntologyToolGateway:
    registry = load_ontology_registry()
    authorization_service = AuthorizationService(registry.permission_registry)
    return _StubGateway(
        session_factory=lambda: nullcontext(),
        registry_provider=lambda: registry,
        authorization_service_provider=lambda: authorization_service,
    )


def _build_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def _run_tool_with_actor(*, server, actor: ActorContext, tool_name: str, arguments: dict[str, object]):
    token = set_current_mcp_actor(actor)
    try:
        return asyncio.run(server.call_tool(tool_name, arguments))
    finally:
        reset_current_mcp_actor(token)


def test_gateway_search_objects_returns_existing_ontology_objects() -> None:
    gateway = _build_gateway()

    result = gateway.search_objects(
        actor=_build_ai_actor(),
        payload=SearchObjectsToolInput(objectType="Supplier"),
    )

    assert result.objectType == "Supplier"
    assert [item.objectId for item in result.items] == ["S-101", "S-102", "S-103"]
    assert result.nextCursor is None
    assert result.hasMore is False


def test_gateway_search_objects_uses_public_object_ids() -> None:
    gateway = _build_gateway()

    result = gateway.search_objects(
        actor=_build_ai_actor(),
        payload=SearchObjectsToolInput(objectType="Supplier"),
    )

    assert result.items[1].objectId == "S-102"
    assert result.items[1].properties["supplierCode"] == "S-102"


def test_gateway_get_object_returns_existing_object() -> None:
    gateway = _build_gateway()

    result = gateway.get_object(
        actor=_build_ai_actor(),
        payload=GetObjectToolInput(objectType="Supplier", objectId="S-102"),
    )

    assert result.objectType == "Supplier"
    assert result.objectId == "S-102"
    assert result.displayName == "Vertex Electronics"


def test_gateway_get_object_returns_not_found_for_missing_object() -> None:
    gateway = _build_gateway()

    with pytest.raises(ObjectNotFoundError):
        gateway.get_object(
            actor=_build_ai_actor(),
            payload=GetObjectToolInput(objectType="Supplier", objectId="S-DOES-NOT-EXIST"),
        )


def test_gateway_get_linked_objects_resolves_known_relationship() -> None:
    gateway = _build_gateway()

    result = gateway.get_linked_objects(
        actor=_build_ai_actor(),
        payload=GetLinkedObjectsToolInput(
            objectType="Supplier",
            objectId="S-102",
            linkType="supplierToPurchaseOrders",
        ),
    )

    assert result.sourceObjectType == "Supplier"
    assert result.sourceObjectId == "S-102"
    assert result.linkType == "supplierToPurchaseOrders"
    assert [item.objectId for item in result.items] == ["PO-200", "PO-201", "PO-202", "PO-203", "PO-204"]


def test_gateway_rejects_unknown_object_type() -> None:
    gateway = _build_gateway()

    with pytest.raises(ObjectTypeNotFoundError):
        gateway.search_objects(
            actor=_build_ai_actor(),
            payload=SearchObjectsToolInput(objectType="UnknownType"),
        )


def test_gateway_rejects_unprivileged_actor() -> None:
    gateway = _build_gateway()

    with pytest.raises(AuthorizationDeniedError):
        gateway.get_object(
            actor=_build_unprivileged_ai_actor(),
            payload=GetObjectToolInput(objectType="Supplier", objectId="S-102"),
        )


def test_http_and_stdio_share_the_same_three_registered_tools() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == ["searchObjects", "getObject", "getLinkedObjects"]


def test_mcp_get_object_tool_returns_structured_supplier_result() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="getObject",
        arguments={"payload": {"objectType": "Supplier", "objectId": "S-102"}},
    )

    assert structured["objectType"] == "Supplier"
    assert structured["objectId"] == "S-102"
    assert structured["displayName"] == "Vertex Electronics"


def test_mcp_get_linked_objects_tool_returns_structured_link_result() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="getLinkedObjects",
        arguments={"payload": {"objectType": "Supplier", "objectId": "S-102", "linkType": "supplierToPurchaseOrders"}},
    )

    assert structured["sourceObjectType"] == "Supplier"
    assert structured["sourceObjectId"] == "S-102"
    assert [item["objectId"] for item in structured["items"]] == ["PO-200", "PO-201", "PO-202", "PO-203", "PO-204"]


def test_mcp_search_objects_tool_returns_public_object_ids() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="searchObjects",
        arguments={"payload": {"objectType": "Supplier"}},
    )

    assert structured["objectType"] == "Supplier"
    assert [item["objectId"] for item in structured["items"]] == ["S-101", "S-102", "S-103"]


def test_mcp_tool_input_cannot_override_actor_context() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    with pytest.raises(ToolError, match="OPERATION_NOT_PERMITTED"):
        _run_tool_with_actor(
            server=server,
            actor=_build_unprivileged_ai_actor(),
            tool_name="getObject",
            arguments={
                "payload": {
                    "objectType": "Supplier",
                    "objectId": "S-102",
                    "roles": ["Admin"],
                    "actorId": "forged-admin",
                    "invocationSource": "internal",
                }
            },
        )


def test_mcp_get_object_tool_returns_unknown_object_type_error() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    with pytest.raises(ToolError, match="OBJECT_TYPE_NOT_FOUND"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="getObject",
            arguments={"payload": {"objectType": "UnknownType", "objectId": "example"}},
        )


def test_mcp_get_linked_objects_tool_returns_unknown_link_type_error() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_build_gateway())

    with pytest.raises(ToolError, match="LINK_NOT_FOUND"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="getLinkedObjects",
            arguments={"payload": {"objectType": "Supplier", "objectId": "S-102", "linkType": "unknownLink"}},
        )
