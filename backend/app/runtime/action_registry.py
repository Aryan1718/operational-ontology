"""Startup builder for the immutable ontology action handler registry."""

from __future__ import annotations

from app.actions.generate_mitigation_plan import generate_mitigation_plan
from app.actions.registry import ActionHandlerRegistry, RegisteredActionHandler
from app.schemas.actions import (
    GenerateMitigationPlanParameters,
    GenerateMitigationPlanResult,
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
        }
    )
