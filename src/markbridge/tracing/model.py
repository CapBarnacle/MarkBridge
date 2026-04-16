"""Trace-oriented monitoring models for parsing workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from markbridge.shared.ir import DocumentFormat


class ParseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class TraceStage(str, Enum):
    INGEST = "ingest"
    INSPECTION = "inspection"
    ROUTING = "routing"
    PARSING = "parsing"
    NORMALIZATION = "normalization"
    VALIDATION = "validation"
    REPAIR = "repair"
    RENDERING = "rendering"
    EXPORT = "export"


class TraceEventKind(str, Enum):
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    COMPONENT_SELECTED = "component_selected"
    ARTIFACT_PRODUCED = "artifact_produced"
    ISSUE_DETECTED = "issue_detected"
    WARNING_EMITTED = "warning_emitted"
    REPAIR_DECISION = "repair_decision"
    STATUS_CHANGED = "status_changed"


class ArtifactKind(str, Enum):
    INSPECTION_REPORT = "inspection_report"
    ROUTING_DECISION = "routing_decision"
    PARSER_OUTPUT = "parser_output"
    NORMALIZED_IR = "normalized_ir"
    VALIDATION_REPORT = "validation_report"
    RENDERED_MARKDOWN = "rendered_markdown"
    METADATA_JSON = "metadata_json"
    TRACE_JSON = "trace_json"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to an artifact emitted by a pipeline stage."""

    kind: ArtifactKind
    label: str
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DisplayExcerpt:
    """Human-readable excerpt for UI display of suspicious content."""

    label: str
    content: str
    mime_type: str = "text/plain"
    highlight_text: str | None = None
    location_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IssueSnapshot:
    """Lightweight issue summary for trace views."""

    issue_id: str
    code: str
    severity: IssueSeverity
    message: str
    stage: TraceStage
    block_ref: str | None = None
    excerpts: tuple[DisplayExcerpt, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Single user-visible event emitted during pipeline execution."""

    event_id: str
    stage: TraceStage
    kind: TraceEventKind
    status: ParseStatus
    timestamp: datetime
    component: str
    message: str
    artifact: ArtifactRef | None = None
    issue: IssueSnapshot | None = None
    excerpts: tuple[DisplayExcerpt, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseTrace:
    """Complete step-by-step trace for one parse attempt."""

    trace_id: str
    source_path: Path
    document_format: DocumentFormat
    status: ParseStatus = ParseStatus.PENDING
    events: tuple[TraceEvent, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, source_path: Path, document_format: DocumentFormat) -> "ParseTrace":
        return cls(
            trace_id=str(uuid4()),
            source_path=source_path,
            document_format=document_format,
        )
