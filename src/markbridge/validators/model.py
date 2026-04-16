"""Validation issue models for deterministic quality checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from markbridge.tracing.model import DisplayExcerpt, IssueSeverity, IssueSnapshot, TraceStage


class ValidationIssueCode(str, Enum):
    TEXT_CORRUPTION = "text_corruption"
    TABLE_STRUCTURE = "table_structure"
    IMAGE_REFERENCE = "image_reference"
    STRUCTURE_TRANSITION = "structure_transition"
    EMPTY_OUTPUT = "empty_output"


class IssueDisposition(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    IGNORED = "ignored"
    REPAIRED = "repaired"


@dataclass(frozen=True, slots=True)
class LocationRef:
    """Source hint for where a validation issue was found."""

    page: int | None = None
    sheet: str | None = None
    block_ref: str | None = None
    table_id: str | None = None
    line_hint: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Canonical issue record produced by validators."""

    issue_id: str
    code: ValidationIssueCode
    severity: IssueSeverity
    stage: TraceStage
    message: str
    disposition: IssueDisposition = IssueDisposition.OPEN
    location: LocationRef | None = None
    excerpts: tuple[DisplayExcerpt, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
    repairable: bool = False

    @classmethod
    def create(
        cls,
        code: ValidationIssueCode,
        severity: IssueSeverity,
        stage: TraceStage,
        message: str,
        *,
        disposition: IssueDisposition = IssueDisposition.OPEN,
        location: LocationRef | None = None,
        excerpts: tuple[DisplayExcerpt, ...] = (),
        details: dict[str, Any] | None = None,
        repairable: bool = False,
    ) -> "ValidationIssue":
        return cls(
            issue_id=str(uuid4()),
            code=code,
            severity=severity,
            stage=stage,
            message=message,
            disposition=disposition,
            location=location,
            excerpts=excerpts,
            details=details or {},
            repairable=repairable,
        )

    def to_snapshot(self) -> IssueSnapshot:
        """Convert a canonical issue into a trace-friendly snapshot."""

        block_ref = self.location.block_ref if self.location else None
        metadata = {
            "disposition": self.disposition.value,
            "repairable": self.repairable,
        }
        if self.details:
            metadata["details"] = self.details
        if self.location:
            metadata["location"] = {
                "page": self.location.page,
                "sheet": self.location.sheet,
                "block_ref": self.location.block_ref,
                "table_id": self.location.table_id,
                "line_hint": self.location.line_hint,
            }

        return IssueSnapshot(
            issue_id=self.issue_id,
            code=self.code.value,
            severity=self.severity,
            message=self.message,
            stage=self.stage,
            block_ref=block_ref,
            excerpts=self.excerpts,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Validation result bundle attached to parse outputs and trace artifacts."""

    issues: tuple[ValidationIssue, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is IssueSeverity.ERROR for issue in self.issues)

    @property
    def has_repairable_issues(self) -> bool:
        return any(issue.repairable for issue in self.issues)
