"""Routing decision models for parser selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteLevel(str, Enum):
    DETERMINISTIC_ONLY = "deterministic_only"
    DETERMINISTIC_WITH_LLM_ROUTING = "deterministic_with_llm_routing"
    DETERMINISTIC_WITH_RECONCILIATION = "deterministic_with_reconciliation"


class LlmUsageMode(str, Enum):
    NONE = "none"
    ROUTING = "routing"
    RECONCILIATION = "reconciliation"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Selected parser route derived from inspection features and policy."""

    level: RouteLevel
    primary_parser: str
    fallback_parsers: tuple[str, ...] = ()
    llm_usage: LlmUsageMode = LlmUsageMode.NONE
    rationale: tuple[str, ...] = ()
    policy_metadata: dict[str, Any] = field(default_factory=dict)
