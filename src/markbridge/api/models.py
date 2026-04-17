"""Pydantic models for the MarkBridge API surface."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from markbridge.api.storage import S3ObjectOption
from markbridge.routing.model import LlmUsageMode, RouteLevel, RoutingDecision
from markbridge.routing.runtime import RuntimeParserStatus
from markbridge.shared.ir import DocumentFormat
from markbridge.tracing.model import (
    ArtifactKind,
    ArtifactRef,
    DisplayExcerpt,
    IssueSeverity,
    IssueSnapshot,
    ParseStatus,
    TraceEvent,
    TraceEventKind,
    TraceStage,
)
from markbridge.validators.gate import HandoffDecision, QualityGateResult


class SourceKind(str, Enum):
    UPLOAD = "upload"
    S3_URI = "s3_uri"


class HealthResponse(BaseModel):
    service: str = "markbridge"
    status: str = "ok"
    api_version: str = "v1"
    llm_configured: bool
    azure_model: str


class RuntimeParserStatusResponse(BaseModel):
    parser_id: str
    installed: bool
    enabled: bool
    reason: str | None = None
    supported_formats: list[DocumentFormat] = Field(default_factory=list)
    route_kind: str = "primary"


class RuntimeStatusResponse(BaseModel):
    parsers: list[RuntimeParserStatusResponse] = Field(default_factory=list)


class S3ObjectOptionResponse(BaseModel):
    label: str
    bucket: str
    key: str
    s3_uri: str
    document_format: DocumentFormat | None = None
    size_bytes: int | None = None
    updated_at: datetime | None = None


class S3ObjectListResponse(BaseModel):
    objects: list[S3ObjectOptionResponse] = Field(default_factory=list)


class S3BucketOptionResponse(BaseModel):
    name: str
    label: str


class S3BucketListResponse(BaseModel):
    buckets: list[S3BucketOptionResponse] = Field(default_factory=list)


class ParseMarkdownExportStatus(str, Enum):
    COMPLETED = "completed"
    RUNNING = "running"
    PENDING = "pending"
    FAILED = "failed"


class ParseMarkdownExportItemResponse(BaseModel):
    document_id: str
    document_name: str
    canonical_markdown_name: str
    parse_status: ParseMarkdownExportStatus
    last_parse_completed_at: datetime | None = None
    markdown_download_url: str


class ParseMarkdownExportListResponse(BaseModel):
    items: list[ParseMarkdownExportItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None


class ParseMarkdownBlockItemResponse(BaseModel):
    block_id: str
    block_index: int
    block_kind: str
    markdown_line_start: int
    markdown_line_end: int
    page_number: int | None = None
    block_download_url: str
    chunk_boundary_candidate: bool = False


class ParseMarkdownBlockListResponse(BaseModel):
    document_id: str
    document_name: str
    canonical_markdown_name: str
    parse_status: ParseMarkdownExportStatus
    last_parse_completed_at: datetime | None = None
    blocks: list[ParseMarkdownBlockItemResponse] = Field(default_factory=list)


class SourceSummary(BaseModel):
    kind: SourceKind
    name: str
    uri: str | None = None
    document_format: DocumentFormat
    size_bytes: int
    content_type: str | None = None


class ExcerptResponse(BaseModel):
    label: str
    content: str
    mime_type: str = "text/plain"
    highlight_text: str | None = None
    location_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IssueResponse(BaseModel):
    issue_id: str
    code: str
    severity: IssueSeverity
    message: str
    stage: TraceStage
    block_ref: str | None = None
    excerpts: list[ExcerptResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    kind: ArtifactKind
    label: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEventResponse(BaseModel):
    event_id: str
    stage: TraceStage
    kind: TraceEventKind
    status: ParseStatus
    timestamp: datetime
    component: str
    message: str
    artifact: ArtifactResponse | None = None
    issue: IssueResponse | None = None
    excerpts: list[ExcerptResponse] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class TraceResponse(BaseModel):
    trace_id: str
    status: ParseStatus
    source: SourceSummary
    events: list[TraceEventResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingResponse(BaseModel):
    level: RouteLevel
    primary_parser: str
    fallback_parsers: list[str] = Field(default_factory=list)
    llm_usage: LlmUsageMode
    rationale: list[str] = Field(default_factory=list)
    policy_metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffResponse(BaseModel):
    decision: HandoffDecision
    summary: str
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class MarkdownLineMapEntryResponse(BaseModel):
    line_number: int
    text: str
    refs: list[str] = Field(default_factory=list)
    page_number: int | None = None


class RepairPatchProposalResponse(BaseModel):
    action: str
    target_text: str
    replacement_text: str
    origin: str | None = None
    block_ref: str | None = None
    location_hint: str | None = None
    markdown_line_number: int | None = None
    confidence: float
    rationale: str
    uncertain: bool = True


class RepairCandidateResponse(BaseModel):
    issue_id: str
    repair_type: str
    strategy: str
    origin: str = "deterministic"
    source_text: str
    source_span: str | None = None
    candidate_text: str | None = None
    normalized_math: str | None = None
    confidence: float
    rationale: str
    requires_review: bool = True
    llm_recommended: bool = True
    block_ref: str | None = None
    markdown_line_number: int | None = None
    location_hint: str | None = None
    severity: str = "warning"
    patch_proposal: RepairPatchProposalResponse | None = None


class DownstreamHandoffResponse(BaseModel):
    policy: str
    preferred_markdown_kind: str
    review_required: bool
    source_markdown_available: bool = True
    suggested_resolved_available: bool = False
    final_resolved_available: bool = False
    rationale: list[str] = Field(default_factory=list)


class ResolutionCandidateDecisionResponse(BaseModel):
    candidate_index: int
    origin: str
    strategy: str | None = None
    confidence: float = 0.0
    selected: bool = False
    patch_available: bool = False
    rejected_reason: str | None = None


class ResolutionIssueDetailResponse(BaseModel):
    issue_id: str
    corruption_class: str | None = None
    resolved: bool
    selected_origin: str | None = None
    selected_confidence: float | None = None
    selection_reason: str | None = None
    llm_requested: bool = False
    llm_attempted: bool = False
    unresolved_reason: str | None = None
    candidate_decisions: list[ResolutionCandidateDecisionResponse] = Field(default_factory=list)


class ResolutionSummaryResponse(BaseModel):
    repair_issue_count: int
    resolved_issue_count: int
    recovered_deterministic_count: int = 0
    recovered_llm_count: int = 0
    unresolved_repair_issue_count: int = 0
    unresolved_by_class: dict[str, int] = Field(default_factory=dict)
    unresolved_by_reason: dict[str, int] = Field(default_factory=dict)
    issues: list[ResolutionIssueDetailResponse] = Field(default_factory=list)


class LlmDiagnosticsResponse(BaseModel):
    routing_used: bool = False
    routing_recommendation: str | None = None
    routing_baseline_parser: str | None = None
    routing_selected_parser: str | None = None
    routing_override_applied: bool = False
    routing_comparison_preview: list[str] = Field(default_factory=list)
    repair_attempted_issues: int = 0
    repair_generated_candidates: int = 0
    repair_error: str | None = None
    repair_response_available: bool = False
    repair_response_preview: list[str] = Field(default_factory=list)
    formula_probe_attempted: bool = False
    formula_probe_error: str | None = None
    formula_probe_apply_as_patch: bool | None = None
    formula_probe_confidence: float | None = None
    formula_probe_region_image_path: str | None = None
    formula_probe_preview: list[str] = Field(default_factory=list)


class ParseEvaluationResponse(BaseModel):
    readiness_score: int
    readiness_label: str
    issue_count: int
    repair_candidate_count: int
    deterministic_candidate_count: int
    llm_candidate_count: int
    suggested_patch_count: int
    recovered_deterministic_count: int = 0
    recovered_llm_count: int = 0
    unresolved_repair_issue_count: int = 0
    review_required: bool
    recommended_next_step: str
    rationale: list[str] = Field(default_factory=list)


class ParseResponse(BaseModel):
    request_id: str
    source: SourceSummary
    routing: RoutingResponse
    handoff: HandoffResponse
    trace: TraceResponse
    issues: list[IssueResponse] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
    markdown: str
    markdown_line_map: list[MarkdownLineMapEntryResponse] = Field(default_factory=list)
    repair_candidates: list[RepairCandidateResponse] = Field(default_factory=list)
    suggested_resolved_markdown: str | None = None
    suggested_resolved_patches: list[RepairPatchProposalResponse] = Field(default_factory=list)
    final_resolved_markdown: str | None = None
    final_resolved_patches: list[RepairPatchProposalResponse] = Field(default_factory=list)
    resolution_summary: ResolutionSummaryResponse
    llm_diagnostics: LlmDiagnosticsResponse
    downstream_handoff: DownstreamHandoffResponse
    evaluation: ParseEvaluationResponse
    llm_requested: bool
    llm_used: bool
    notes: list[str] = Field(default_factory=list)


class S3ParseRequest(BaseModel):
    s3_uri: str
    llm_requested: bool = False
    parser_hint: str | None = None


def trace_event_from_domain(event: TraceEvent) -> TraceEventResponse:
    return TraceEventResponse(
        event_id=event.event_id,
        stage=event.stage,
        kind=event.kind,
        status=event.status,
        timestamp=event.timestamp,
        component=event.component,
        message=event.message,
        artifact=artifact_from_domain(event.artifact) if event.artifact else None,
        issue=issue_from_domain(event.issue) if event.issue else None,
        excerpts=[excerpt_from_domain(excerpt) for excerpt in event.excerpts],
        data=event.data,
    )


def issue_from_domain(issue: IssueSnapshot) -> IssueResponse:
    return IssueResponse(
        issue_id=issue.issue_id,
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        stage=issue.stage,
        block_ref=issue.block_ref,
        excerpts=[excerpt_from_domain(excerpt) for excerpt in issue.excerpts],
        metadata=issue.metadata,
    )


def excerpt_from_domain(excerpt: DisplayExcerpt) -> ExcerptResponse:
    return ExcerptResponse(
        label=excerpt.label,
        content=excerpt.content,
        mime_type=excerpt.mime_type,
        highlight_text=excerpt.highlight_text,
        location_hint=excerpt.location_hint,
        metadata=excerpt.metadata,
    )


def artifact_from_domain(artifact: ArtifactRef) -> ArtifactResponse:
    return ArtifactResponse(
        kind=artifact.kind,
        label=artifact.label,
        path=str(artifact.path) if artifact.path else None,
        metadata=artifact.metadata,
    )


def routing_from_domain(routing: RoutingDecision) -> RoutingResponse:
    return RoutingResponse(
        level=routing.level,
        primary_parser=routing.primary_parser,
        fallback_parsers=list(routing.fallback_parsers),
        llm_usage=routing.llm_usage,
        rationale=list(routing.rationale),
        policy_metadata=routing.policy_metadata,
    )


def handoff_from_domain(handoff: QualityGateResult) -> HandoffResponse:
    return HandoffResponse(
        decision=handoff.decision,
        summary=handoff.summary,
        reasons=list(handoff.reasons),
        metadata=handoff.metadata,
    )


def runtime_status_from_domain(status: RuntimeParserStatus) -> RuntimeParserStatusResponse:
    return RuntimeParserStatusResponse(
        parser_id=status.parser_id,
        installed=status.installed,
        enabled=status.enabled,
        reason=status.reason,
        supported_formats=list(status.supported_formats),
        route_kind=status.route_kind,
    )


def s3_object_option_from_domain(item: S3ObjectOption) -> S3ObjectOptionResponse:
    return S3ObjectOptionResponse(
        label=item.label,
        bucket=item.bucket,
        key=item.key,
        s3_uri=item.s3_uri,
        document_format=item.document_format,
        size_bytes=item.size_bytes,
        updated_at=item.updated_at,
    )
