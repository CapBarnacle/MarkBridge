"""Pipeline orchestration scaffolding for MarkBridge."""

from .events import (
    append_event,
    artifact_produced,
    build_stage_event,
    component_selected,
    issue_detected,
    stage_completed,
    stage_started,
    status_changed,
)
from .models import (
    PipelineArtifactBundle,
    PipelineRequest,
    PipelineResult,
    PipelineStageResult,
)
from .orchestrator import run_pipeline
from markbridge.tracing.flow import STANDARD_TRACE_FLOW

__all__ = [
    "PipelineArtifactBundle",
    "PipelineRequest",
    "PipelineResult",
    "PipelineStageResult",
    "append_event",
    "artifact_produced",
    "build_stage_event",
    "component_selected",
    "issue_detected",
    "STANDARD_TRACE_FLOW",
    "run_pipeline",
    "stage_completed",
    "stage_started",
    "status_changed",
]
