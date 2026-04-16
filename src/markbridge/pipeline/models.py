"""Pipeline-level request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from markbridge.parsers.base import ParseRequest
from markbridge.routing.model import RoutingDecision
from markbridge.shared.ir import DocumentFormat, DocumentIR
from markbridge.tracing.model import ArtifactRef, ParseStatus, ParseTrace
from markbridge.validators.gate import HandoffDecision, QualityGateResult
from markbridge.validators.model import ValidationReport


@dataclass(frozen=True, slots=True)
class PipelineRequest:
    """Top-level request passed into the pipeline orchestrator."""

    source_path: Path
    document_format: DocumentFormat
    options: dict[str, Any] = field(default_factory=dict)
    parse_request: ParseRequest | None = None

    @classmethod
    def from_parse_request(cls, request: ParseRequest) -> "PipelineRequest":
        return cls(
            source_path=request.source_path,
            document_format=request.document_format,
            options=dict(request.options),
            parse_request=request,
        )


@dataclass(frozen=True, slots=True)
class PipelineArtifactBundle:
    """Grouped artifacts produced during a pipeline run."""

    inspection: ArtifactRef | None = None
    routing: ArtifactRef | None = None
    parser_output: ArtifactRef | None = None
    normalized_ir: ArtifactRef | None = None
    validation: ArtifactRef | None = None
    markdown: ArtifactRef | None = None
    metadata: ArtifactRef | None = None
    trace: ArtifactRef | None = None


@dataclass(frozen=True, slots=True)
class PipelineStageResult:
    """Reusable stage result for the orchestrator skeleton."""

    stage: str
    status: ParseStatus
    message: str
    artifact: ArtifactRef | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Full pipeline output bundle."""

    run_id: str
    request: PipelineRequest
    trace: ParseTrace
    route: RoutingDecision | None
    validation: ValidationReport
    handoff: QualityGateResult
    document: DocumentIR | None = None
    artifacts: PipelineArtifactBundle = field(default_factory=PipelineArtifactBundle)
    parser_id: str | None = None
    warnings: tuple[str, ...] = ()
    status: ParseStatus = ParseStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def decision(self) -> HandoffDecision:
        return self.handoff.decision

    @classmethod
    def create(
        cls,
        request: PipelineRequest,
        trace: ParseTrace,
        *,
        route: RoutingDecision | None,
        validation: ValidationReport,
        handoff: QualityGateResult,
        document: DocumentIR | None = None,
        artifacts: PipelineArtifactBundle | None = None,
        parser_id: str | None = None,
        warnings: tuple[str, ...] = (),
        status: ParseStatus = ParseStatus.PENDING,
        metadata: dict[str, Any] | None = None,
    ) -> "PipelineResult":
        return cls(
            run_id=str(uuid4()),
            request=request,
            trace=trace,
            route=route,
            validation=validation,
            handoff=handoff,
            document=document,
            artifacts=artifacts or PipelineArtifactBundle(),
            parser_id=parser_id,
            warnings=warnings,
            status=status,
            metadata=metadata or {},
        )
