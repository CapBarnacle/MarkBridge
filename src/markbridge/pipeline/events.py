"""Trace event helpers for pipeline orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from markbridge.tracing.model import (
    ArtifactRef,
    DisplayExcerpt,
    IssueSnapshot,
    ParseStatus,
    ParseTrace,
    TraceEvent,
    TraceEventKind,
    TraceStage,
)


def build_stage_event(
    *,
    stage: TraceStage,
    kind: TraceEventKind,
    component: str,
    message: str,
    status: ParseStatus,
    artifact: ArtifactRef | None = None,
    issue: IssueSnapshot | None = None,
    excerpts: tuple[DisplayExcerpt, ...] = (),
    data: dict[str, object] | None = None,
    timestamp: datetime | None = None,
) -> TraceEvent:
    """Create a single trace event with a stable timestamp policy."""

    return TraceEvent(
        event_id=str(uuid4()),
        stage=stage,
        kind=kind,
        status=status,
        timestamp=timestamp or datetime.now(timezone.utc),
        component=component,
        message=message,
        artifact=artifact,
        issue=issue,
        excerpts=excerpts,
        data=data or {},
    )


def append_event(trace: ParseTrace, event: TraceEvent, *, status: ParseStatus | None = None) -> ParseTrace:
    """Append a trace event and optionally update the trace status."""

    updated_status = status or event.status
    return replace(
        trace,
        status=updated_status,
        events=trace.events + (event,),
    )


def status_changed(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    status: ParseStatus,
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a status transition."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.STATUS_CHANGED,
        component=component,
        message=message,
        status=status,
        data=data,
    )
    return append_event(trace, event, status=status)


def component_selected(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    status: ParseStatus = ParseStatus.RUNNING,
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a selected component or parser route."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.COMPONENT_SELECTED,
        component=component,
        message=message,
        status=status,
        data=data,
    )
    return append_event(trace, event, status=status)


def artifact_produced(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    status: ParseStatus,
    artifact: ArtifactRef | None = None,
    issue: IssueSnapshot | None = None,
    excerpts: tuple[DisplayExcerpt, ...] = (),
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a produced artifact."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.ARTIFACT_PRODUCED,
        component=component,
        message=message,
        status=status,
        artifact=artifact,
        issue=issue,
        excerpts=excerpts,
        data=data,
    )
    return append_event(trace, event, status=status)


def issue_detected(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    status: ParseStatus,
    issue: IssueSnapshot,
    excerpts: tuple[DisplayExcerpt, ...] = (),
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a validation or repair issue."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.ISSUE_DETECTED,
        component=component,
        message=message,
        status=status,
        issue=issue,
        excerpts=excerpts,
        data=data,
    )
    return append_event(trace, event, status=status)


def stage_started(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a stage start event."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.STAGE_STARTED,
        component=component,
        message=message,
        status=ParseStatus.RUNNING,
        data=data,
    )
    return append_event(trace, event, status=ParseStatus.RUNNING)


def stage_completed(
    trace: ParseTrace,
    *,
    stage: TraceStage,
    component: str,
    message: str,
    status: ParseStatus,
    artifact: ArtifactRef | None = None,
    issue: IssueSnapshot | None = None,
    excerpts: tuple[DisplayExcerpt, ...] = (),
    data: dict[str, object] | None = None,
) -> ParseTrace:
    """Record a stage completion event."""

    event = build_stage_event(
        stage=stage,
        kind=TraceEventKind.STAGE_COMPLETED,
        component=component,
        message=message,
        status=status,
        artifact=artifact,
        issue=issue,
        excerpts=excerpts,
        data=data,
    )
    return append_event(trace, event, status=status)
