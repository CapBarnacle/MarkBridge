"""Initial deterministic validation rule registry."""

from __future__ import annotations

from dataclasses import dataclass

from markbridge.tracing import IssueSeverity, TraceStage
from markbridge.validators.model import ValidationIssueCode


@dataclass(frozen=True, slots=True)
class ValidationRule:
    """Declarative description of a deterministic validation rule."""

    rule_id: str
    issue_code: ValidationIssueCode
    severity: IssueSeverity
    stage: TraceStage
    description: str
    repairable: bool


INITIAL_VALIDATION_RULES: tuple[ValidationRule, ...] = (
    ValidationRule(
        rule_id="text.replacement_characters",
        issue_code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        description="Flags suspicious replacement characters or broken text fragments.",
        repairable=True,
    ),
    ValidationRule(
        rule_id="text.empty_output",
        issue_code=ValidationIssueCode.EMPTY_OUTPUT,
        severity=IssueSeverity.ERROR,
        stage=TraceStage.VALIDATION,
        description="Flags documents or blocks that produced unexpectedly empty output.",
        repairable=False,
    ),
    ValidationRule(
        rule_id="table.header_missing",
        issue_code=ValidationIssueCode.TABLE_STRUCTURE,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        description="Flags table-like structures that appear to have missing or collapsed headers.",
        repairable=True,
    ),
    ValidationRule(
        rule_id="table.shape_inconsistent",
        issue_code=ValidationIssueCode.TABLE_STRUCTURE,
        severity=IssueSeverity.ERROR,
        stage=TraceStage.VALIDATION,
        description="Flags inconsistent row or cell structure that suggests table corruption.",
        repairable=True,
    ),
    ValidationRule(
        rule_id="image.weak_reference",
        issue_code=ValidationIssueCode.IMAGE_REFERENCE,
        severity=IssueSeverity.INFO,
        stage=TraceStage.VALIDATION,
        description="Flags image references that have weak captions, anchors, or surrounding context.",
        repairable=True,
    ),
    ValidationRule(
        rule_id="structure.heading_jump",
        issue_code=ValidationIssueCode.STRUCTURE_TRANSITION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        description="Flags suspicious heading or block-order transitions.",
        repairable=False,
    ),
)
