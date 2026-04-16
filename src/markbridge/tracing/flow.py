"""Standard trace event flow for the parsing pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from markbridge.tracing.model import TraceEventKind, TraceStage


@dataclass(frozen=True, slots=True)
class TraceFlowStep:
    """Declarative step in the standard pipeline trace flow."""

    step_id: str
    stage: TraceStage
    kind: TraceEventKind
    description: str


STANDARD_TRACE_FLOW: tuple[TraceFlowStep, ...] = (
    TraceFlowStep("ingest.started", TraceStage.INGEST, TraceEventKind.STAGE_STARTED, "Document intake begins."),
    TraceFlowStep("ingest.completed", TraceStage.INGEST, TraceEventKind.STAGE_COMPLETED, "Document intake completed."),
    TraceFlowStep("inspection.started", TraceStage.INSPECTION, TraceEventKind.STAGE_STARTED, "Deterministic inspection begins."),
    TraceFlowStep("inspection.artifact", TraceStage.INSPECTION, TraceEventKind.ARTIFACT_PRODUCED, "Inspection report was produced."),
    TraceFlowStep("inspection.completed", TraceStage.INSPECTION, TraceEventKind.STAGE_COMPLETED, "Deterministic inspection completed."),
    TraceFlowStep("routing.started", TraceStage.ROUTING, TraceEventKind.STAGE_STARTED, "Routing evaluation begins."),
    TraceFlowStep("routing.component_selected", TraceStage.ROUTING, TraceEventKind.COMPONENT_SELECTED, "Parser route was selected."),
    TraceFlowStep("routing.artifact", TraceStage.ROUTING, TraceEventKind.ARTIFACT_PRODUCED, "Routing decision artifact was produced."),
    TraceFlowStep("routing.completed", TraceStage.ROUTING, TraceEventKind.STAGE_COMPLETED, "Routing evaluation completed."),
    TraceFlowStep("parsing.started", TraceStage.PARSING, TraceEventKind.STAGE_STARTED, "Parser execution begins."),
    TraceFlowStep("parsing.artifact", TraceStage.PARSING, TraceEventKind.ARTIFACT_PRODUCED, "Parser output artifact was produced."),
    TraceFlowStep("parsing.completed", TraceStage.PARSING, TraceEventKind.STAGE_COMPLETED, "Parser execution completed."),
    TraceFlowStep("normalization.started", TraceStage.NORMALIZATION, TraceEventKind.STAGE_STARTED, "IR normalization begins."),
    TraceFlowStep("normalization.artifact", TraceStage.NORMALIZATION, TraceEventKind.ARTIFACT_PRODUCED, "Normalized IR artifact was produced."),
    TraceFlowStep("normalization.completed", TraceStage.NORMALIZATION, TraceEventKind.STAGE_COMPLETED, "IR normalization completed."),
    TraceFlowStep("validation.started", TraceStage.VALIDATION, TraceEventKind.STAGE_STARTED, "Validation begins."),
    TraceFlowStep("validation.issue_detected", TraceStage.VALIDATION, TraceEventKind.ISSUE_DETECTED, "Validation issue was detected."),
    TraceFlowStep("validation.artifact", TraceStage.VALIDATION, TraceEventKind.ARTIFACT_PRODUCED, "Validation report artifact was produced."),
    TraceFlowStep("validation.completed", TraceStage.VALIDATION, TraceEventKind.STAGE_COMPLETED, "Validation completed."),
    TraceFlowStep("repair.decision", TraceStage.REPAIR, TraceEventKind.REPAIR_DECISION, "Repair or reconciliation decision was recorded."),
    TraceFlowStep("rendering.started", TraceStage.RENDERING, TraceEventKind.STAGE_STARTED, "Markdown rendering begins."),
    TraceFlowStep("rendering.artifact", TraceStage.RENDERING, TraceEventKind.ARTIFACT_PRODUCED, "Rendered Markdown artifact was produced."),
    TraceFlowStep("rendering.completed", TraceStage.RENDERING, TraceEventKind.STAGE_COMPLETED, "Markdown rendering completed."),
    TraceFlowStep("export.started", TraceStage.EXPORT, TraceEventKind.STAGE_STARTED, "Final artifact export begins."),
    TraceFlowStep("export.artifact", TraceStage.EXPORT, TraceEventKind.ARTIFACT_PRODUCED, "Trace or metadata export artifact was produced."),
    TraceFlowStep("export.completed", TraceStage.EXPORT, TraceEventKind.STAGE_COMPLETED, "Final artifact export completed."),
)
