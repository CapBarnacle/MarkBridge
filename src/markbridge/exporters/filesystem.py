"""Filesystem export helpers for MarkBridge artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Inputs needed to persist a single pipeline run."""

    run_id: str
    work_root: Path
    markdown: str
    trace: object
    issues: tuple[object, ...] = ()
    manifest: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ExportedArtifactSet:
    """Paths produced by a filesystem export."""

    run_dir: Path
    markdown_path: Path
    trace_path: Path
    issues_path: Path
    manifest_path: Path


def export_run_artifacts(request: ExportRequest) -> ExportedArtifactSet:
    """Persist run artifacts into a run-specific directory under the work root."""

    run_dir = request.work_root / request.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = run_dir / "result.md"
    trace_path = run_dir / "trace.json"
    issues_path = run_dir / "issues.json"
    manifest_path = run_dir / "manifest.json"

    markdown_path.write_text(request.markdown, encoding="utf-8")
    trace_path.write_text(json.dumps(_to_jsonable(request.trace), indent=2, ensure_ascii=False), encoding="utf-8")
    issues_path.write_text(json.dumps([_to_jsonable(issue) for issue in request.issues], indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "run_id": request.run_id,
        "run_dir": str(run_dir),
        "artifacts": {
            "markdown": str(markdown_path),
            "trace": str(trace_path),
            "issues": str(issues_path),
        },
        "counts": {
            "issues": len(request.issues),
        },
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    if request.manifest:
        manifest["metadata"] = _to_jsonable(dict(request.manifest))

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return ExportedArtifactSet(
        run_dir=run_dir,
        markdown_path=markdown_path,
        trace_path=trace_path,
        issues_path=issues_path,
        manifest_path=manifest_path,
    )


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "__dict__"):
        return {
            key: _to_jsonable(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)
