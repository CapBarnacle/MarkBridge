"""Validation checks for rendered and normalized output."""

from .gate import HandoffDecision, QualityGateResult, evaluate_handoff
from .execution import validate_document
from .model import (
    IssueDisposition,
    LocationRef,
    ValidationIssue,
    ValidationIssueCode,
    ValidationReport,
)
from .rules import INITIAL_VALIDATION_RULES, ValidationRule

__all__ = [
    "evaluate_handoff",
    "HandoffDecision",
    "INITIAL_VALIDATION_RULES",
    "IssueDisposition",
    "LocationRef",
    "QualityGateResult",
    "ValidationRule",
    "ValidationIssue",
    "ValidationIssueCode",
    "ValidationReport",
    "validate_document",
]
