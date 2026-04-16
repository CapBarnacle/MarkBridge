"""Quality gate models for downstream handoff decisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from markbridge.tracing import IssueSeverity
from markbridge.validators.model import ValidationReport


class HandoffDecision(str, Enum):
    ACCEPT = "accept"
    DEGRADED_ACCEPT = "degraded_accept"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    """Decision about whether parse output may proceed downstream."""

    decision: HandoffDecision
    summary: str
    reasons: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


def evaluate_handoff(report: ValidationReport) -> QualityGateResult:
    """Apply the initial downstream handoff policy to a validation report."""

    if any(issue.severity is IssueSeverity.ERROR for issue in report.issues):
        return QualityGateResult(
            decision=HandoffDecision.HOLD,
            summary="Hold downstream handoff because error-level validation issues exist.",
            reasons=_unique_reasons(issue.code.value for issue in report.issues if issue.severity is IssueSeverity.ERROR),
        )

    if any(issue.severity is IssueSeverity.WARNING for issue in report.issues):
        return QualityGateResult(
            decision=HandoffDecision.DEGRADED_ACCEPT,
            summary="Allow downstream handoff with degraded status because warning-level issues exist.",
            reasons=_unique_reasons(issue.code.value for issue in report.issues if issue.severity is IssueSeverity.WARNING),
        )

    return QualityGateResult(
        decision=HandoffDecision.ACCEPT,
        summary="Allow downstream handoff because no blocking validation issues were found.",
    )


def _unique_reasons(values: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for value in values:
        if value in ordered:
            continue
        ordered.append(value)
    return tuple(ordered)
