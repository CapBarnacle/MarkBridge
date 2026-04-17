"""Backend-first pipeline orchestration."""

from __future__ import annotations

from dataclasses import replace

from markbridge.config import load_settings
from markbridge.exporters import ExportRequest, export_run_artifacts
from markbridge.inspection.basic import inspect_document
from markbridge.inspection.model import InspectionReport
from markbridge.parsers.base import ParseRequest
from markbridge.parsers.basic import parse_with_current_runtime
from markbridge.repairs.formula import generate_repair_candidates
from markbridge.renderers.markdown import render_markdown_with_map
from markbridge.routing.runtime import choose_route, get_runtime_statuses
from markbridge.routing.model import RouteLevel, RoutingDecision
from markbridge.shared.ir import DocumentFormat, DocumentIR
from markbridge.tracing.flow import STANDARD_TRACE_FLOW
from markbridge.tracing.model import ArtifactKind, ArtifactRef, IssueSeverity, ParseStatus, ParseTrace, TraceStage
from markbridge.validators.gate import HandoffDecision, QualityGateResult, evaluate_handoff
from markbridge.validators.execution import validate_document
from markbridge.validators.model import ValidationIssue, ValidationIssueCode, ValidationReport

from .events import artifact_produced, component_selected, issue_detected, stage_completed, stage_started, status_changed
from .models import PipelineArtifactBundle, PipelineRequest, PipelineResult


def _build_initial_trace(request: PipelineRequest) -> ParseTrace:
    return ParseTrace.create(request.source_path, request.document_format)


def _build_parse_request(request: PipelineRequest) -> ParseRequest:
    if request.parse_request is not None:
        return request.parse_request
    return ParseRequest(
        source_path=request.source_path,
        document_format=request.document_format,
        options=dict(request.options),
    )


def _attach_inspection(parse_request: ParseRequest, inspection: InspectionReport) -> ParseRequest:
    if parse_request.inspection is inspection:
        return parse_request
    return ParseRequest(
        source_path=parse_request.source_path,
        document_format=parse_request.document_format,
        inspection=inspection,
        options=dict(parse_request.options),
    )


def _apply_route_quality_adjustment(handoff: QualityGateResult, *, parser_id: str) -> QualityGateResult:
    status = get_runtime_statuses().get(parser_id)
    if status is None:
        return handoff
    if status.route_kind not in {"degraded_fallback", "text_route"}:
        return handoff
    if handoff.decision is HandoffDecision.HOLD:
        return handoff

    reasons = list(handoff.reasons)
    if "degraded_parser_route" not in reasons:
        reasons.append("degraded_parser_route")
    metadata = dict(handoff.metadata)
    metadata["parser_route_kind"] = status.route_kind
    metadata["parser_id"] = parser_id
    if handoff.decision is HandoffDecision.ACCEPT:
        return QualityGateResult(
            decision=HandoffDecision.DEGRADED_ACCEPT,
            summary=(
                "Allow downstream handoff with degraded status because the selected parser route is "
                f"{status.route_kind}."
            ),
            reasons=tuple(reasons),
            metadata=metadata,
        )
    return QualityGateResult(
        decision=handoff.decision,
        summary=handoff.summary,
        reasons=tuple(reasons),
        metadata=metadata,
    )


def run_pipeline(request: PipelineRequest) -> PipelineResult:
    """Run the current pipeline while preserving trace visibility."""

    trace = _build_initial_trace(request)
    trace = stage_started(
        trace,
        stage=TraceStage.INGEST,
        component="pipeline.orchestrator",
        message="Pipeline execution started.",
        data={"source_path": str(request.source_path)},
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.INGEST,
        component="pipeline.orchestrator",
        message="Document intake completed.",
        status=ParseStatus.SUCCEEDED,
        data={"source_path": str(request.source_path)},
    )

    inspection = inspect_document(request.source_path, request.document_format)
    trace = stage_started(
        trace,
        stage=TraceStage.INSPECTION,
        component="pipeline.orchestrator",
        message="Deterministic inspection started.",
    )
    trace = artifact_produced(
        trace,
        stage=TraceStage.INSPECTION,
        component="inspection.basic",
        message="Inspection report produced.",
        status=ParseStatus.SUCCEEDED,
        artifact=ArtifactRef(kind=ArtifactKind.INSPECTION_REPORT, label="inspection-report"),
        data={"warnings": inspection.warnings},
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.INSPECTION,
        component="pipeline.orchestrator",
        message="Inspection completed.",
        status=ParseStatus.SUCCEEDED,
        data={"document_format": request.document_format.value},
    )

    route = choose_route(
        inspection,
        parser_override=request.options.get("parser_override"),
        llm_used=bool(request.options.get("llm_route_used")),
    )
    trace = stage_started(
        trace,
        stage=TraceStage.ROUTING,
        component="pipeline.orchestrator",
        message="Routing evaluation started.",
    )
    trace = component_selected(
        trace,
        stage=TraceStage.ROUTING,
        component="routing.runtime",
        message=f"Selected parser route: {route.primary_parser}",
        data={"rationale": route.rationale},
    )
    trace = artifact_produced(
        trace,
        stage=TraceStage.ROUTING,
        component="routing.runtime",
        message="Routing decision produced.",
        status=ParseStatus.SUCCEEDED,
        artifact=ArtifactRef(kind=ArtifactKind.ROUTING_DECISION, label="routing-decision"),
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.ROUTING,
        component="pipeline.orchestrator",
        message="Routing completed.",
        status=ParseStatus.SUCCEEDED,
        data={"primary_parser": route.primary_parser, "level": route.level.value},
    )

    parse_request = _attach_inspection(_build_parse_request(request), inspection)
    trace = stage_started(
        trace,
        stage=TraceStage.PARSING,
        component="pipeline.orchestrator",
        message="Parser execution started.",
    )
    if route.primary_parser == "unsupported":
        unsupported_issue = ValidationIssue.create(
            code=ValidationIssueCode.EMPTY_OUTPUT,
            severity=IssueSeverity.ERROR,
            stage=TraceStage.PARSING,
            message=f"No enabled parser route is available for {request.document_format.value}.",
            repairable=False,
            details={"document_format": request.document_format.value},
        )
        validation = ValidationReport(
            issues=(unsupported_issue,),
            summary={"unsupported_format": request.document_format.value, "issue_count": 1},
        )
        handoff = QualityGateResult(
            decision=HandoffDecision.HOLD,
            summary=f"No enabled parser route is available for {request.document_format.value}.",
            reasons=("unsupported_route",),
        )
        trace = issue_detected(
            trace,
            stage=TraceStage.PARSING,
            component="pipeline.orchestrator",
            message=unsupported_issue.message,
            status=ParseStatus.FAILED,
            issue=unsupported_issue.to_snapshot(),
        )
        trace = status_changed(
            trace,
            stage=TraceStage.PARSING,
            component="pipeline.orchestrator",
            message="Parsing could not start because no enabled parser route exists.",
            status=ParseStatus.FAILED,
            data={"document_format": request.document_format.value},
        )
        return PipelineResult.create(
            request=request,
            trace=trace,
            route=route,
            validation=validation,
            handoff=handoff,
            document=None,
            artifacts=PipelineArtifactBundle(),
            parser_id=None,
            warnings=("No enabled parser route is available.",),
            status=ParseStatus.FAILED,
            metadata={"trace_flow_steps": len(STANDARD_TRACE_FLOW)},
        )

    parse_result = parse_with_current_runtime(parse_request, route.primary_parser)
    document = parse_result.document
    trace = artifact_produced(
        trace,
        stage=TraceStage.PARSING,
        component=f"parsers.basic:{route.primary_parser}",
        message="Parser output produced.",
        status=ParseStatus.SUCCEEDED,
        artifact=ArtifactRef(kind=ArtifactKind.PARSER_OUTPUT, label="parser-output"),
        data={"block_count": len(document.blocks)},
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.PARSING,
        component="pipeline.orchestrator",
        message="Parsing completed.",
        status=ParseStatus.SUCCEEDED,
        data={"parser_id": route.primary_parser, "block_count": len(document.blocks)},
    )

    trace = stage_started(
        trace,
        stage=TraceStage.NORMALIZATION,
        component="pipeline.orchestrator",
        message="Normalization started.",
    )
    trace = artifact_produced(
        trace,
        stage=TraceStage.NORMALIZATION,
        component="pipeline.orchestrator",
        message="Normalized IR produced.",
        status=ParseStatus.SUCCEEDED,
        artifact=ArtifactRef(kind=ArtifactKind.NORMALIZED_IR, label="normalized-ir"),
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.NORMALIZATION,
        component="pipeline.orchestrator",
        message="Normalization completed.",
        status=ParseStatus.SUCCEEDED,
    )

    markdown_render = render_markdown_with_map(document)
    markdown_text = markdown_render.markdown
    validation = validate_document(document, markdown_text=markdown_text)
    repair_candidates = generate_repair_candidates(validation.issues)
    trace = stage_started(
        trace,
        stage=TraceStage.VALIDATION,
        component="pipeline.orchestrator",
        message="Validation started.",
    )
    for issue in validation.issues:
        issue_status = ParseStatus.FAILED if issue.severity.name == "ERROR" else ParseStatus.DEGRADED
        trace = issue_detected(
            trace,
            stage=TraceStage.VALIDATION,
            component="validators.execution",
            message=issue.message,
            status=issue_status,
            issue=issue.to_snapshot(),
            excerpts=issue.excerpts,
        )
    trace = artifact_produced(
        trace,
        stage=TraceStage.VALIDATION,
        component="validators.execution",
        message="Validation report produced.",
        status=ParseStatus.DEGRADED if validation.issues else ParseStatus.SUCCEEDED,
        artifact=ArtifactRef(kind=ArtifactKind.VALIDATION_REPORT, label="validation-report"),
        data=validation.summary,
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.VALIDATION,
        component="pipeline.orchestrator",
        message="Validation completed.",
        status=ParseStatus.DEGRADED if validation.issues else ParseStatus.SUCCEEDED,
        data={"issue_count": len(validation.issues)},
    )

    handoff = _apply_route_quality_adjustment(evaluate_handoff(validation), parser_id=route.primary_parser)
    if handoff.decision.value == "hold":
        final_status = ParseStatus.FAILED
    elif handoff.decision.value == "degraded_accept":
        final_status = ParseStatus.DEGRADED
    else:
        final_status = ParseStatus.SUCCEEDED

    trace = replace(
        trace,
        metadata={
            "handoff_decision": handoff.decision.value,
            "inspection_format": request.document_format.value,
            "markdown_length": len(markdown_text),
        },
    )
    trace = stage_started(
        trace,
        stage=TraceStage.REPAIR,
        component="pipeline.orchestrator",
        message="Repair decision evaluation started.",
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.REPAIR,
        component="pipeline.orchestrator",
        message="Repair decision recorded.",
        status=final_status,
        data={"decision": handoff.decision.value, "repair_candidate_count": len(repair_candidates)},
    )
    trace = stage_started(
        trace,
        stage=TraceStage.RENDERING,
        component="pipeline.orchestrator",
        message="Rendering started.",
    )
    trace = artifact_produced(
        trace,
        stage=TraceStage.RENDERING,
        component="renderers.markdown",
        message="Markdown output produced.",
        status=final_status,
        artifact=ArtifactRef(kind=ArtifactKind.RENDERED_MARKDOWN, label="rendered-markdown"),
        data={"characters": len(markdown_text)},
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.RENDERING,
        component="pipeline.orchestrator",
        message="Rendering completed.",
        status=final_status,
    )
    trace = stage_started(
        trace,
        stage=TraceStage.EXPORT,
        component="pipeline.orchestrator",
        message="Export started.",
    )
    result = PipelineResult.create(
        request=request,
        trace=trace,
        route=route,
        validation=validation,
        handoff=handoff,
        document=document,
        artifacts=PipelineArtifactBundle(),
        parser_id=route.primary_parser,
        warnings=parse_result.warnings,
        status=final_status,
        metadata={
            "inspection": inspection.__class__.__name__,
            "parse_request": parse_request.__class__.__name__,
            "trace_flow_steps": len(STANDARD_TRACE_FLOW),
            "markdown": markdown_text,
            "repair_candidates": [candidate.as_dict() for candidate in repair_candidates],
            "markdown_line_map": [
                {
                    "line_number": item.line_number,
                    "text": item.text,
                    "refs": list(item.refs),
                }
                for item in markdown_render.line_map
            ],
        },
    )
    settings = load_settings()
    exported = export_run_artifacts(
        ExportRequest(
            run_id=result.run_id,
            work_root=settings.storage.work_dir,
            markdown=markdown_text,
            trace=trace,
            issues=validation.issues,
            manifest={
                "source_path": str(request.source_path),
                "source_name": str(request.options.get("source_name") or request.source_path.name),
                "source_uri": request.options.get("source_uri"),
                "document_format": request.document_format.value,
                "parser_id": route.primary_parser,
                "handoff_decision": handoff.decision.value,
                "status": final_status.value,
            },
        )
    )
    artifacts = PipelineArtifactBundle(
        inspection=ArtifactRef(kind=ArtifactKind.INSPECTION_REPORT, label="inspection-report"),
        routing=ArtifactRef(kind=ArtifactKind.ROUTING_DECISION, label="routing-decision"),
        parser_output=ArtifactRef(kind=ArtifactKind.PARSER_OUTPUT, label="parser-output"),
        normalized_ir=ArtifactRef(kind=ArtifactKind.NORMALIZED_IR, label="normalized-ir"),
        validation=ArtifactRef(kind=ArtifactKind.VALIDATION_REPORT, label="validation-report", path=exported.issues_path),
        markdown=ArtifactRef(kind=ArtifactKind.RENDERED_MARKDOWN, label="rendered-markdown", path=exported.markdown_path),
        metadata=ArtifactRef(kind=ArtifactKind.METADATA_JSON, label="manifest", path=exported.manifest_path),
        trace=ArtifactRef(kind=ArtifactKind.TRACE_JSON, label="trace", path=exported.trace_path),
    )
    trace = artifact_produced(
        trace,
        stage=TraceStage.EXPORT,
        component="pipeline.orchestrator",
        message="Artifact bundle recorded.",
        status=final_status,
        artifact=ArtifactRef(kind=ArtifactKind.TRACE_JSON, label="trace", path=exported.trace_path),
    )
    trace = stage_completed(
        trace,
        stage=TraceStage.EXPORT,
        component="pipeline.orchestrator",
        message="Export completed.",
        status=final_status,
        data={"artifact_bundle": "ready"},
    )

    return PipelineResult.create(
        request=request,
        trace=trace,
        route=route,
        validation=validation,
        handoff=handoff,
        document=document,
        artifacts=artifacts,
        parser_id=route.primary_parser,
        warnings=parse_result.warnings,
        status=final_status,
        metadata={
            **result.metadata,
            "export_dir": str(exported.run_dir),
            "source_name": str(request.options.get("source_name") or request.source_path.name),
            "source_uri": request.options.get("source_uri"),
        },
    )
