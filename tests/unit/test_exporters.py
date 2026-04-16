from pathlib import Path

from markbridge.exporters import ExportRequest, export_run_artifacts
from markbridge.shared.ir import DocumentFormat
from markbridge.tracing import ParseTrace, ParseStatus
from markbridge.validators.model import ValidationReport


def test_export_run_artifacts_writes_expected_files(tmp_path: Path) -> None:
    trace = ParseTrace.create(Path("sample.docx"), DocumentFormat.DOCX)
    trace = ParseTrace(
        trace_id=trace.trace_id,
        source_path=trace.source_path,
        document_format=trace.document_format,
        status=ParseStatus.SUCCEEDED,
        events=trace.events,
        warnings=("example warning",),
        metadata={"source": "test"},
    )
    issues = ()

    exported = export_run_artifacts(
        ExportRequest(
            run_id="run-123",
            work_root=tmp_path,
            markdown="# Title\n\nBody",
            trace=trace,
            issues=issues,
            manifest={"pipeline": "markbridge"},
        )
    )

    assert exported.run_dir.exists()
    assert exported.markdown_path.read_text(encoding="utf-8") == "# Title\n\nBody"
    assert exported.trace_path.exists()
    assert exported.issues_path.exists()
    assert exported.manifest_path.exists()


def test_export_run_artifacts_serializes_dataclasses(tmp_path: Path) -> None:
    trace = ParseTrace.create(Path("sample.pdf"), DocumentFormat.PDF)
    report = ValidationReport(summary={"ok": True})

    exported = export_run_artifacts(
        ExportRequest(
            run_id="run-456",
            work_root=tmp_path,
            markdown="Hello",
            trace=trace,
            issues=tuple(report.issues),
        )
    )

    trace_body = exported.trace_path.read_text(encoding="utf-8")
    manifest_body = exported.manifest_path.read_text(encoding="utf-8")
    assert "\"trace_id\"" in trace_body
    assert "\"issues\": 0" in manifest_body
