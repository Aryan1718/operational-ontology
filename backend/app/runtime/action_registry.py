"""Startup builder for the immutable ontology action handler registry."""

from __future__ import annotations

from app.actions.approve_mitigation_plan import approve_mitigation_plan
from app.actions.expedite_purchase_order import expedite_purchase_order
from app.actions.generate_mitigation_plan import generate_mitigation_plan
from app.actions.reallocate_inventory import reallocate_inventory
from app.actions.registry import ActionHandlerRegistry, RegisteredActionHandler
from app.schemas.actions import (
    ApproveMitigationPlanParameters,
    ApproveMitigationPlanResult,
    ExpeditePurchaseOrderParameters,
    ExpeditePurchaseOrderResult,
    GenerateMitigationPlanParameters,
    GenerateMitigationPlanResult,
    ReallocateInventoryParameters,
    ReallocateInventoryResult,
)


def build_action_handler_registry() -> ActionHandlerRegistry:
    """Build the immutable registry of executable ontology actions."""
    return ActionHandlerRegistry(
        {
            "generateMitigationPlan": RegisteredActionHandler(
                handler_name="generateMitigationPlan",
                input_model=GenerateMitigationPlanParameters,
                output_model=GenerateMitigationPlanResult,
                execute=generate_mitigation_plan,
            ),
            "approveMitigationPlan": RegisteredActionHandler(
                handler_name="approveMitigationPlan",
                input_model=ApproveMitigationPlanParameters,
                output_model=ApproveMitigationPlanResult,
                execute=approve_mitigation_plan,
            ),
            "reallocateInventory": RegisteredActionHandler(
                handler_name="reallocateInventory",
                input_model=ReallocateInventoryParameters,
                output_model=ReallocateInventoryResult,
                execute=reallocate_inventory,
            ),
            "expeditePurchaseOrder": RegisteredActionHandler(
                handler_name="expeditePurchaseOrder",
                input_model=ExpeditePurchaseOrderParameters,
                output_model=ExpeditePurchaseOrderResult,
                execute=expedite_purchase_order,
            ),
        }
    )
