"""Shared MCP server construction for HTTP and stdio transports."""

from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import ApplicationError
from app.mcp.context import get_current_mcp_actor
from app.mcp.ontology_tool_gateway import (
    GetLinkedObjectsToolInput,
    GetObjectToolInput,
    OntologyToolGateway,
    SearchObjectsToolInput,
    build_default_ontology_tool_gateway,
)
from app.schemas.functions import (
    CalculateStockoutRiskParameters,
    FindAlternativeWarehousesParameters,
    FindExpeditablePurchaseOrdersParameters,
    FindImpactedOrdersParameters,
    FindImpactedPartsParameters,
    FindImpactedProductsParameters,
    GetInventoryAvailabilityParameters,
    RankImpactedOrdersParameters,
    RecommendMitigationPlanParameters,
)


@dataclass(frozen=True)
class McpServerDefinition:
    """Static Phase 1 MCP server metadata shared across transports."""

    name: str
    instructions: str


@dataclass(frozen=True)
class FunctionToolDefinition:
    """Static metadata for one read-only ontology function tool."""

    name: str
    description: str
    input_model: type[BaseModel]


FUNCTION_TOOL_DEFINITIONS: tuple[FunctionToolDefinition, ...] = (
    FunctionToolDefinition(
        name="findImpactedParts",
        description="Find parts impacted by a disruption event using the existing ontology function runtime.",
        input_model=FindImpactedPartsParameters,
    ),
    FunctionToolDefinition(
        name="findImpactedProducts",
        description="Find products impacted by a disruption event using the existing ontology function runtime.",
        input_model=FindImpactedProductsParameters,
    ),
    FunctionToolDefinition(
        name="findImpactedOrders",
        description="Find customer orders impacted by a disruption event using the existing ontology function runtime.",
        input_model=FindImpactedOrdersParameters,
    ),
    FunctionToolDefinition(
        name="calculateStockoutRisk",
        description="Calculate projected stockout risk for a part at a warehouse using the existing ontology function runtime.",
        input_model=CalculateStockoutRiskParameters,
    ),
    FunctionToolDefinition(
        name="getInventoryAvailability",
        description="Summarize current inventory availability for a part using the existing ontology function runtime.",
        input_model=GetInventoryAvailabilityParameters,
    ),
    FunctionToolDefinition(
        name="findAlternativeWarehouses",
        description="Find feasible source warehouses for inventory transfer using the existing ontology function runtime.",
        input_model=FindAlternativeWarehousesParameters,
    ),
    FunctionToolDefinition(
        name="findExpeditablePurchaseOrders",
        description="Find feasible purchase orders that can be expedited using the existing ontology function runtime.",
        input_model=FindExpeditablePurchaseOrdersParameters,
    ),
    FunctionToolDefinition(
        name="rankImpactedOrders",
        description="Rank impacted customer orders using the existing ontology function runtime.",
        input_model=RankImpactedOrdersParameters,
    ),
    FunctionToolDefinition(
        name="recommendMitigationPlan",
        description="Recommend a read-only mitigation strategy using the existing ontology function runtime.",
        input_model=RecommendMitigationPlanParameters,
    ),
)


def get_mcp_server_definition() -> McpServerDefinition:
    """Return the single Operational Ontology MCP server definition."""
    return McpServerDefinition(
        name="Operational Ontology",
        instructions=(
            "Operational Ontology MCP foundation. Phase 3 exposes read-only object "
            "search, object retrieval, declared link traversal, and approved ontology "
            "function execution through the shared runtime and authorization service."
        ),
    )


def create_mcp_server(
    settings: Settings,
    *,
    ontology_tool_gateway: OntologyToolGateway | None = None,
) -> FastMCP:
    """Create the shared MCP server used by both HTTP and stdio transports."""
    del settings
    definition = get_mcp_server_definition()
    server = FastMCP(
        definition.name,
        instructions=definition.instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
    gateway = ontology_tool_gateway or build_default_ontology_tool_gateway()

    @server.tool(
        name="searchObjects",
        description=(
            "Search one ontology object type using the existing metadata-driven "
            "object runtime. This is a read-only operation."
        ),
    )
    def search_objects(payload: SearchObjectsToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.search_objects(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    @server.tool(
        name="getObject",
        description=(
            "Get one ontology object by object type and public object ID using the "
            "existing object runtime. This is a read-only operation."
        ),
    )
    def get_object(payload: GetObjectToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.get_object(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    @server.tool(
        name="getLinkedObjects",
        description=(
            "Traverse one declared ontology link from a source object using the "
            "existing link runtime. This is a read-only operation."
        ),
    )
    def get_linked_objects(payload: GetLinkedObjectsToolInput) -> dict[str, object]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.get_linked_objects(actor=actor, payload=payload).model_dump(
                mode="json",
                by_alias=True,
            )
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc

    for definition in FUNCTION_TOOL_DEFINITIONS:
        _register_function_tool(server=server, gateway=gateway, definition=definition)

    return server


def _register_function_tool(
    *,
    server: FastMCP,
    gateway: OntologyToolGateway,
    definition: FunctionToolDefinition,
) -> None:
    @server.tool(name=definition.name, description=definition.description)
    def _function_tool(payload: definition.input_model) -> dict[str, Any]:
        actor = _require_current_mcp_actor()
        try:
            return gateway.execute_function(
                actor=actor,
                function_name=definition.name,
                payload=payload,
            ).model_dump(mode="json", by_alias=True)
        except ApplicationError as exc:
            raise _tool_error_from_application_error(exc) from exc


def _require_current_mcp_actor():
    actor = get_current_mcp_actor()
    if actor is None:
        raise ToolError("MCP actor context is not available.")
    return actor


def _tool_error_from_application_error(exc: ApplicationError) -> ToolError:
    return ToolError(f"{exc.code}: {exc.message}")
