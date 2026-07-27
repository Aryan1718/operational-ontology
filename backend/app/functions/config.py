"""Shared ontology-function configuration defaults."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OrderRankingWeights:
    order_priority: Decimal
    delivery_urgency: Decimal
    shortage_ratio: Decimal
    projected_delay: Decimal
    order_value: Decimal
    part_criticality: Decimal


@dataclass(frozen=True, slots=True)
class OntologyFunctionConfig:
    order_ranking_weights: OrderRankingWeights
    maximum_projected_delay_score_days: Decimal


DEFAULT_ONTOLOGY_FUNCTION_CONFIG = OntologyFunctionConfig(
    order_ranking_weights=OrderRankingWeights(
        order_priority=Decimal("0.25"),
        delivery_urgency=Decimal("0.20"),
        shortage_ratio=Decimal("0.20"),
        projected_delay=Decimal("0.15"),
        order_value=Decimal("0.10"),
        part_criticality=Decimal("0.10"),
    ),
    maximum_projected_delay_score_days=Decimal("10"),
)
