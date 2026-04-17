"""API service that bridges inputs to the MarkBridge pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import base64
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
import re

from markbridge.api.config import ApiSettings
from markbridge.api.llm import AzureLlmAdvisor, LlmAdvice
from markbridge.api.models import (
    ArtifactResponse,
    DownstreamHandoffResponse,
    LlmDiagnosticsResponse,
    ParseMarkdownBlockItemResponse,
    ParseMarkdownBlockListResponse,
    ParseMarkdownExportItemResponse,
    ParseMarkdownExportListResponse,
    ParseMarkdownExportStatus,
    MarkdownLineMapEntryResponse,
    ParseResponse,
    ParseEvaluationResponse,
    RepairCandidateResponse,
    RepairPatchProposalResponse,
    ResolutionCandidateDecisionResponse,
    ResolutionIssueDetailResponse,
    ResolutionSummaryResponse,
    SourceKind,
    SourceSummary,
    handoff_from_domain,
    issue_from_domain,
    routing_from_domain,
    trace_event_from_domain,
)
from markbridge.api.storage import download_s3_uri_to_tempfile
from markbridge.config import load_settings
from markbridge.experiments.formula_probe import run_first_formula_probe
from markbridge.inspection.model import InspectionReport
from markbridge.inspection import inspect_document
from markbridge.pipeline import PipelineRequest, PipelineResult, run_pipeline
from markbridge.routing.runtime import executable_candidates_for_format
from markbridge.shared.ir import DocumentFormat
from markbridge.validators.execution import FORMULA_PLACEHOLDER


SUPPORTED_SUFFIXES: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".doc": DocumentFormat.DOC,
    ".hwp": DocumentFormat.HWP,
}

FORMULA_REPAIR_CLASSES = {
    "inline_formula_corruption",
    "table_formula_corruption",
    "formula_placeholder",
    "structure_loss",
}


@dataclass(frozen=True, slots=True)
class AcquiredSource:
    source_kind: SourceKind
    source_name: str
    uri: str | None
    path: Path
    document_format: DocumentFormat
    size_bytes: int
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class ExportDocumentRecord:
    document_id: str
    document_name: str
    canonical_markdown_name: str
    parse_status: ParseMarkdownExportStatus
    last_parse_completed_at: datetime | None
    markdown_download_url: str
    run_dir: Path
    canonical_markdown_path: Path
    line_map_path: Path | None = None


class MarkBridgePipeline:
    """API-facing adapter around the domain pipeline."""

    def __init__(self, settings: ApiSettings) -> None:
        self._settings = settings
        self._llm = AzureLlmAdvisor(settings) if settings.llm_configured else None
        self._work_root = load_settings().storage.work_dir

    def list_parse_markdown_exports(
        self,
        *,
        updated_after: datetime | None = None,
        limit: int = 100,
        cursor: str | None = None,
        parse_status: ParseMarkdownExportStatus | None = None,
    ) -> ParseMarkdownExportListResponse:
        documents = [
            item
            for item in self._load_latest_export_documents().values()
            if self._is_listable_export_document(item.document_name)
        ]
        if parse_status is not None:
            documents = [item for item in documents if item.parse_status == parse_status]
        if updated_after is not None:
            documents = [
                item
                for item in documents
                if item.last_parse_completed_at is not None and item.last_parse_completed_at > updated_after
            ]
        documents.sort(
            key=lambda item: (
                item.last_parse_completed_at.timestamp() if item.last_parse_completed_at else 0.0,
                item.document_id,
            ),
            reverse=True,
        )

        offset = self._decode_cursor(cursor)
        sliced = documents[offset : offset + limit]
        next_offset = offset + len(sliced)
        next_cursor = self._encode_cursor(next_offset) if next_offset < len(documents) else None
        return ParseMarkdownExportListResponse(
            items=[
                ParseMarkdownExportItemResponse(
                    document_id=item.document_id,
                    document_name=item.document_name,
                    canonical_markdown_name=item.canonical_markdown_name,
                    parse_status=item.parse_status,
                    last_parse_completed_at=item.last_parse_completed_at,
                    markdown_download_url=item.markdown_download_url,
                )
                for item in sliced
            ],
            next_cursor=next_cursor,
        )

    def get_parse_markdown_export(self, document_id: str) -> ExportDocumentRecord:
        documents = self._load_latest_export_documents()
        try:
            return documents[document_id]
        except KeyError as exc:
            raise ValueError(f"Unknown document_id: {document_id}") from exc

    def get_parse_markdown_content(self, document_id: str) -> tuple[ExportDocumentRecord, str, str]:
        document = self.get_parse_markdown_export(document_id)
        if document.parse_status != ParseMarkdownExportStatus.COMPLETED:
            raise RuntimeError(f"Document is not downloadable in status={document.parse_status.value}")
        content = document.canonical_markdown_path.read_text(encoding="utf-8")
        etag = self._etag_for_text(content)
        return document, content, etag

    def list_parse_markdown_blocks(self, document_id: str) -> ParseMarkdownBlockListResponse:
        document, markdown, _ = self.get_parse_markdown_content(document_id)
        line_map = self._load_markdown_line_map(document.line_map_path)
        blocks = self._build_canonical_blocks(
            document=document,
            markdown=markdown,
            line_map=line_map,
        )
        return ParseMarkdownBlockListResponse(
            document_id=document.document_id,
            document_name=document.document_name,
            canonical_markdown_name=document.canonical_markdown_name,
            parse_status=document.parse_status,
            last_parse_completed_at=document.last_parse_completed_at,
            blocks=blocks,
        )

    def get_parse_markdown_block_content(self, document_id: str, block_id: str) -> tuple[ExportDocumentRecord, str, str]:
        document, markdown, _ = self.get_parse_markdown_content(document_id)
        line_map = self._load_markdown_line_map(document.line_map_path)
        blocks = self._build_canonical_blocks(
            document=document,
            markdown=markdown,
            line_map=line_map,
        )
        for block in blocks:
            if block.block_id == block_id:
                content = self._slice_markdown_lines(markdown, block.markdown_line_start, block.markdown_line_end)
                return document, content, self._etag_for_text(content)
        raise ValueError(f"Unknown block_id: {block_id}")

    def _load_latest_export_documents(self) -> dict[str, ExportDocumentRecord]:
        latest_by_document: dict[str, ExportDocumentRecord] = {}
        if not self._work_root.exists():
            return latest_by_document

        for record in self._iter_export_documents():
            current = latest_by_document.get(record.document_id)
            if current is None:
                latest_by_document[record.document_id] = record
                continue
            current_ts = current.last_parse_completed_at.timestamp() if current.last_parse_completed_at else 0.0
            record_ts = record.last_parse_completed_at.timestamp() if record.last_parse_completed_at else 0.0
            if record_ts >= current_ts:
                latest_by_document[record.document_id] = record
        return latest_by_document

    def _iter_export_documents(self) -> list[ExportDocumentRecord]:
        records: list[ExportDocumentRecord] = []
        for run_dir in sorted(self._work_root.iterdir()) if self._work_root.exists() else []:
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            metadata = manifest.get("metadata") or {}
            source_name = str(metadata.get("source_name") or "document")
            source_uri = metadata.get("source_uri")
            document_id = self._document_id_for_source(source_name=source_name, source_uri=source_uri)
            canonical_name = self._canonical_markdown_filename_for_source_name(source_name)
            canonical_path = run_dir / canonical_name
            status = self._normalize_external_parse_status(str(metadata.get("status") or "failed"))
            if not canonical_path.exists() and status is ParseMarkdownExportStatus.COMPLETED:
                status = ParseMarkdownExportStatus.FAILED
            timestamp = self._parse_manifest_timestamp(
                manifest.get("created_at"),
                metadata.get("completed_at"),
            )
            records.append(
                ExportDocumentRecord(
                    document_id=document_id,
                    document_name=source_name,
                    canonical_markdown_name=canonical_name,
                    parse_status=status,
                    last_parse_completed_at=timestamp,
                    markdown_download_url=f"/exports/parse-markdown/{document_id}/content",
                    run_dir=run_dir,
                    canonical_markdown_path=canonical_path,
                    line_map_path=(run_dir / "markdown_line_map.json") if (run_dir / "markdown_line_map.json").exists() else None,
                )
            )
        return records

    def _document_id_for_source(self, *, source_name: str, source_uri: str | None) -> str:
        stable_key = source_uri or source_name
        digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:12]
        return f"doc_{digest}"

    def _is_listable_export_document(self, source_name: str) -> bool:
        normalized = Path(str(source_name) or "").name.strip().lower()
        if not normalized:
            return False
        if normalized == "sample.docx":
            return False
        if normalized.startswith("tmp"):
            return False
        if normalized.startswith("markbridge_"):
            return False
        return True

    def _canonical_markdown_filename_for_source_name(self, source_name: str) -> str:
        source_path = Path(str(source_name) or "document")
        full_name = source_path.name or "document"
        sanitized = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]', "_", full_name).strip()
        sanitized = sanitized.rstrip(". ") or "document"
        return f"{sanitized}-1.md"

    def _normalize_external_parse_status(self, status: str) -> ParseMarkdownExportStatus:
        normalized = status.lower().strip()
        if normalized in {"succeeded", "degraded", "completed"}:
            return ParseMarkdownExportStatus.COMPLETED
        if normalized == "running":
            return ParseMarkdownExportStatus.RUNNING
        if normalized == "pending":
            return ParseMarkdownExportStatus.PENDING
        return ParseMarkdownExportStatus.FAILED

    def _parse_manifest_timestamp(self, *candidates: object) -> datetime | None:
        for candidate in candidates:
            if not candidate:
                continue
            try:
                text = str(candidate)
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                return datetime.fromisoformat(text)
            except ValueError:
                continue
        return None

    def _encode_cursor(self, offset: int) -> str:
        payload = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    def _decode_cursor(self, cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            payload = base64.urlsafe_b64decode(cursor.encode("ascii"))
            decoded = json.loads(payload.decode("utf-8"))
            offset = int(decoded.get("offset", 0))
            return max(0, offset)
        except Exception:
            return 0

    def _etag_for_text(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _load_markdown_line_map(self, line_map_path: Path | None) -> list[dict[str, object]]:
        if line_map_path is None or not line_map_path.exists():
            return []
        try:
            payload = json.loads(line_map_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _build_canonical_blocks(
        self,
        *,
        document: ExportDocumentRecord,
        markdown: str,
        line_map: list[dict[str, object]],
    ) -> list[ParseMarkdownBlockItemResponse]:
        lines = markdown.splitlines()
        blocks: list[ParseMarkdownBlockItemResponse] = []
        start_index: int | None = None
        current_kind: str | None = None
        block_index = 0

        def flush(end_index: int) -> None:
            nonlocal start_index, current_kind, block_index
            if start_index is None:
                return
            block_lines = lines[start_index:end_index]
            if not any(line.strip() for line in block_lines):
                start_index = None
                current_kind = None
                return
            block_index += 1
            line_start = start_index + 1
            line_end = end_index
            block_kind = current_kind or self._detect_block_kind(block_lines)
            blocks.append(
                ParseMarkdownBlockItemResponse(
                    block_id=f"block-{block_index:04d}",
                    block_index=block_index,
                    block_kind=block_kind,
                    markdown_line_start=line_start,
                    markdown_line_end=line_end,
                    page_number=self._page_number_for_range(line_map, line_start, line_end),
                    block_download_url=f"/exports/parse-markdown/{document.document_id}/blocks/block-{block_index:04d}/content",
                    chunk_boundary_candidate=block_kind == "heading",
                )
            )
            start_index = None
            current_kind = None

        for idx, line in enumerate(lines):
            line_kind = self._detect_line_kind(line)
            if line_kind == "blank":
                flush(idx)
                continue
            if line_kind == "heading":
                flush(idx)
                start_index = idx
                current_kind = "heading"
                flush(idx + 1)
                continue
            if start_index is None:
                start_index = idx
                current_kind = line_kind
                continue
            if line_kind != current_kind:
                flush(idx)
                start_index = idx
                current_kind = line_kind
        flush(len(lines))
        return blocks

    def _detect_line_kind(self, line: str) -> str:
        stripped = line.lstrip()
        if not stripped:
            return "blank"
        if stripped.startswith("#"):
            return "heading"
        if stripped.startswith(">"):
            return "note"
        if stripped.startswith("|"):
            return "table"
        if stripped.startswith(("- ", "* ")):
            return "list"
        if re.match(r"^\d+\.\s+\S", stripped):
            return "list"
        return "paragraph"

    def _detect_block_kind(self, block_lines: list[str]) -> str:
        first = (block_lines[0] if block_lines else "").lstrip()
        stripped_lines = [line.strip() for line in block_lines if line.strip()]
        if first.startswith("#"):
            return "heading"
        if first.startswith(">"):
            return "note"
        if stripped_lines and all(line.startswith("|") for line in stripped_lines):
            return "table"
        if first.startswith(("- ", "* ")):
            return "list"
        if re.match(r"^\d+\.\s+\S", first):
            return "list"
        return "paragraph"

    def _page_number_for_range(
        self,
        line_map: list[dict[str, object]],
        line_start: int,
        line_end: int,
    ) -> int | None:
        page_counts: Counter[int] = Counter()
        for item in line_map:
            line_number = item.get("line_number")
            page_number = item.get("page_number")
            if not isinstance(line_number, int) or not isinstance(page_number, int):
                continue
            if line_start <= line_number <= line_end:
                page_counts[page_number] += 1
        if not page_counts:
            return None
        return page_counts.most_common(1)[0][0]

    def _slice_markdown_lines(self, markdown: str, line_start: int, line_end: int) -> str:
        lines = markdown.splitlines()
        return "\n".join(lines[line_start - 1 : line_end])

    def submit_local_upload(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None = None,
        llm_requested: bool = False,
        parser_hint: str | None = None,
    ) -> ParseResponse:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file extension: {suffix or '<none>'}")

        with NamedTemporaryFile(prefix="markbridge_upload_", suffix=suffix, delete=False) as handle:
            handle.write(content)
            path = Path(handle.name)

        acquired = AcquiredSource(
            source_kind=SourceKind.UPLOAD,
            source_name=filename,
            uri=None,
            path=path,
            document_format=SUPPORTED_SUFFIXES[suffix],
            size_bytes=len(content),
            content_type=content_type,
        )
        return self._submit(acquired, llm_requested=llm_requested, parser_hint=parser_hint)

    def submit_s3_uri(
        self,
        *,
        s3_uri: str,
        llm_requested: bool = False,
        parser_hint: str | None = None,
    ) -> ParseResponse:
        suffix = Path(s3_uri).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file extension in S3 URI: {suffix or '<none>'}")

        path = download_s3_uri_to_tempfile(s3_uri, suffix=suffix)
        acquired = AcquiredSource(
            source_kind=SourceKind.S3_URI,
            source_name=Path(s3_uri).name or s3_uri,
            uri=s3_uri,
            path=path,
            document_format=SUPPORTED_SUFFIXES[suffix],
            size_bytes=path.stat().st_size,
        )
        return self._submit(acquired, llm_requested=llm_requested, parser_hint=parser_hint)

    def _submit(
        self,
        source: AcquiredSource,
        *,
        llm_requested: bool,
        parser_hint: str | None,
    ) -> ParseResponse:
        preflight_inspection = inspect_document(source.path, source.document_format)
        routing_advice = self._maybe_recommend_routing(
            source,
            preflight_inspection=preflight_inspection,
            llm_requested=llm_requested,
            parser_hint=parser_hint,
        )
        result, routing_probe = self._select_pipeline_result(
            source,
            llm_requested=llm_requested,
            parser_hint=parser_hint,
            routing_advice=routing_advice,
        )
        repair_candidates = self._build_repair_candidates(result)
        llm_repair_candidates, llm_repair_record = self._maybe_recommend_repair(
            source,
            result,
            repair_candidates=repair_candidates,
            llm_requested=llm_requested,
        )
        combined_repair_candidates = repair_candidates + llm_repair_candidates
        final_resolved_markdown, final_resolved_patches = self._build_suggested_resolved_markdown(
            markdown=str(result.metadata.get("markdown", "")),
            repair_candidates=combined_repair_candidates,
        )
        resolution_summary = self._build_resolution_summary(
            issues=result.validation.issues,
            repair_candidates=combined_repair_candidates,
            final_resolved_patches=final_resolved_patches,
            llm_requested=llm_requested,
            llm_repair_record=llm_repair_record,
        )
        downstream_handoff = self._build_downstream_handoff(
            handoff_decision=result.decision.value,
            markdown=str(result.metadata.get("markdown", "")),
            final_resolved_markdown=final_resolved_markdown,
            final_resolved_patches=final_resolved_patches,
            repair_candidates=combined_repair_candidates,
            resolution_summary=resolution_summary,
        )
        evaluation = self._build_parse_evaluation(
            issue_count=len(result.validation.issues),
            repair_candidates=combined_repair_candidates,
            final_resolved_patches=final_resolved_patches,
            downstream_handoff=downstream_handoff,
            resolution_summary=resolution_summary,
        )
        persisted_paths = self._persist_repair_outputs(
            result,
            repair_candidates=combined_repair_candidates,
            llm_repair_record=llm_repair_record,
            markdown_line_map=[
                item for item in result.metadata.get("markdown_line_map", []) if isinstance(item, dict)
            ],
            suggested_resolved_markdown=final_resolved_markdown,
            suggested_resolved_patches=final_resolved_patches,
            final_resolved_markdown=final_resolved_markdown,
            final_resolved_patches=final_resolved_patches,
            resolution_summary=resolution_summary,
            downstream_handoff=downstream_handoff,
            evaluation=evaluation,
        )
        formula_probe_record = self._maybe_run_formula_probe(
            final_resolved_markdown=final_resolved_markdown,
            llm_requested=llm_requested,
            persisted_paths=persisted_paths,
        )
        notes = self._build_notes(
            source,
            result,
            routing_advice,
            repair_candidates=combined_repair_candidates,
            llm_repair_candidates=llm_repair_candidates,
            llm_repair_record=llm_repair_record,
            persisted_paths=persisted_paths,
        )
        return self._to_response(
            source=source,
            result=result,
            llm_requested=llm_requested,
            llm_used=routing_advice.used or bool(llm_repair_candidates),
            routing_advice=routing_advice,
            routing_probe=routing_probe,
            llm_repair_record=llm_repair_record,
            notes=notes,
            repair_candidates=combined_repair_candidates,
            suggested_resolved_markdown=final_resolved_markdown,
            suggested_resolved_patches=final_resolved_patches,
            final_resolved_markdown=final_resolved_markdown,
            final_resolved_patches=final_resolved_patches,
            resolution_summary=resolution_summary,
            downstream_handoff=downstream_handoff,
            evaluation=evaluation,
            formula_probe_record=formula_probe_record,
        )

    def _run_pipeline_for_parser(
        self,
        source: AcquiredSource,
        *,
        llm_requested: bool,
        parser_hint: str | None,
        parser_override: str | None,
        llm_route_used: bool,
    ) -> PipelineResult:
        pipeline_request = PipelineRequest(
            source_path=source.path,
            document_format=source.document_format,
            options={
                "source_kind": source.source_kind.value,
                "source_name": source.source_name,
                "source_uri": source.uri,
                "llm_requested": llm_requested,
                "parser_hint": parser_hint,
                "parser_override": parser_override,
                "llm_route_used": llm_route_used,
            },
        )
        return run_pipeline(pipeline_request)

    def _select_pipeline_result(
        self,
        source: AcquiredSource,
        *,
        llm_requested: bool,
        parser_hint: str | None,
        routing_advice: LlmAdvice,
    ) -> tuple[PipelineResult, dict[str, object] | None]:
        parser_override = self._resolve_parser_override(
            source.document_format,
            parser_hint=parser_hint,
            routing_advice=routing_advice,
        )
        if parser_hint and parser_override == parser_hint:
            result = self._run_pipeline_for_parser(
                source,
                llm_requested=llm_requested,
                parser_hint=parser_hint,
                parser_override=parser_override,
                llm_route_used=False,
            )
            return result, {
                "baseline_parser": result.parser_id,
                "recommended_parser": routing_advice.recommendation,
                "selected_parser": result.parser_id,
                "override_applied": False,
                "comparison_preview": ["parser_hint_forced_selection"],
            }

        baseline_result = self._run_pipeline_for_parser(
            source,
            llm_requested=llm_requested,
            parser_hint=parser_hint,
            parser_override=None,
            llm_route_used=False,
        )
        baseline_parser = baseline_result.parser_id
        recommended_parser = routing_advice.recommendation if routing_advice.used else None
        if not recommended_parser or recommended_parser == baseline_parser:
            return baseline_result, {
                "baseline_parser": baseline_parser,
                "recommended_parser": recommended_parser,
                "selected_parser": baseline_parser,
                "override_applied": False,
                "comparison_preview": ["baseline_parser_retained"],
            }

        candidate_result = self._run_pipeline_for_parser(
            source,
            llm_requested=llm_requested,
            parser_hint=parser_hint,
            parser_override=recommended_parser,
            llm_route_used=True,
        )
        baseline_quality = self._summarize_pipeline_quality(baseline_result)
        candidate_quality = self._summarize_pipeline_quality(candidate_result)
        override_applied = self._should_accept_routing_override(
            baseline_quality=baseline_quality,
            candidate_quality=candidate_quality,
        )
        selected_result = candidate_result if override_applied else baseline_result
        return selected_result, {
            "baseline_parser": baseline_parser,
            "recommended_parser": recommended_parser,
            "selected_parser": selected_result.parser_id,
            "override_applied": override_applied,
            "comparison_preview": self._build_routing_comparison_preview(
                baseline_quality=baseline_quality,
                candidate_quality=candidate_quality,
                override_applied=override_applied,
            ),
        }

    def _summarize_pipeline_quality(self, result: PipelineResult) -> dict[str, object]:
        markdown = str(result.metadata.get("markdown", ""))
        lines = markdown.splitlines() if markdown else []
        nonempty_lines = [line for line in lines if line.strip()]
        heading_count = sum(1 for line in nonempty_lines if line.lstrip().startswith("#"))
        long_line_count = sum(1 for line in nonempty_lines if len(line) >= 180)
        very_long_line_count = sum(1 for line in nonempty_lines if len(line) >= 400)
        text_corruption_issues = [issue for issue in result.validation.issues if issue.code.value == "text_corruption"]
        private_use_count = sum(
            int(getattr(issue, "details", {}).get("private_use_count", 0) or 0)
            for issue in text_corruption_issues
        )
        formula_placeholder_count = sum(
            1
            for issue in text_corruption_issues
            if str(getattr(issue, "details", {}).get("corruption_class", "") or "") == "formula_placeholder"
        )
        error_count = sum(1 for issue in result.validation.issues if issue.severity.name == "ERROR")
        nonempty_count = max(len(nonempty_lines), 1)
        long_line_ratio = long_line_count / nonempty_count
        very_long_line_ratio = very_long_line_count / nonempty_count
        corruption_density = len(text_corruption_issues) / nonempty_count
        formula_placeholder_density = formula_placeholder_count / nonempty_count

        score = 100.0
        score -= error_count * 25.0
        score -= corruption_density * 55.0
        score -= formula_placeholder_density * 35.0
        score -= min(private_use_count / max(nonempty_count, 1) / 12.0, 12.0)
        score -= long_line_ratio * 70.0
        score -= very_long_line_ratio * 45.0
        if heading_count == 0 and len(nonempty_lines) >= 8:
            score -= 28.0
        else:
            score += min(heading_count, 12) * 2.0
        if nonempty_lines:
            average_line_length = sum(len(line) for line in nonempty_lines) / nonempty_count
            if average_line_length >= 140:
                score -= min((average_line_length - 140.0) / 3.0, 25.0)
        else:
            average_line_length = 0.0

        return {
            "parser_id": result.parser_id,
            "score": round(score, 2),
            "heading_count": heading_count,
            "long_line_ratio": round(long_line_ratio, 4),
            "very_long_line_ratio": round(very_long_line_ratio, 4),
            "average_line_length": round(average_line_length, 2),
            "issue_count": len(result.validation.issues),
            "text_corruption_count": len(text_corruption_issues),
            "private_use_count": private_use_count,
        }

    def _should_accept_routing_override(
        self,
        *,
        baseline_quality: dict[str, object],
        candidate_quality: dict[str, object],
    ) -> bool:
        baseline_score = float(baseline_quality.get("score", 0.0))
        candidate_score = float(candidate_quality.get("score", 0.0))
        return candidate_score >= baseline_score + 5.0

    def _build_routing_comparison_preview(
        self,
        *,
        baseline_quality: dict[str, object],
        candidate_quality: dict[str, object],
        override_applied: bool,
    ) -> list[str]:
        baseline_parser = str(baseline_quality.get("parser_id", "baseline"))
        candidate_parser = str(candidate_quality.get("parser_id", "candidate"))
        preview = [
            f"baseline={baseline_parser} score={baseline_quality.get('score', 0.0)}",
            f"recommended={candidate_parser} score={candidate_quality.get('score', 0.0)}",
        ]
        heading_delta = int(candidate_quality.get("heading_count", 0)) - int(baseline_quality.get("heading_count", 0))
        corruption_delta = int(candidate_quality.get("text_corruption_count", 0)) - int(
            baseline_quality.get("text_corruption_count", 0)
        )
        long_line_delta = float(candidate_quality.get("long_line_ratio", 0.0)) - float(
            baseline_quality.get("long_line_ratio", 0.0)
        )
        if heading_delta != 0:
            preview.append(
                f"heading_count {baseline_quality.get('heading_count', 0)} -> {candidate_quality.get('heading_count', 0)}"
            )
        if corruption_delta != 0:
            preview.append(
                "text_corruption_count "
                f"{baseline_quality.get('text_corruption_count', 0)} -> {candidate_quality.get('text_corruption_count', 0)}"
            )
        if abs(long_line_delta) >= 0.05:
            preview.append(
                f"long_line_ratio {baseline_quality.get('long_line_ratio', 0.0)} -> {candidate_quality.get('long_line_ratio', 0.0)}"
            )
        average_line_delta = float(candidate_quality.get("average_line_length", 0.0)) - float(
            baseline_quality.get("average_line_length", 0.0)
        )
        if abs(average_line_delta) >= 20.0:
            preview.append(
                "average_line_length "
                f"{baseline_quality.get('average_line_length', 0.0)} -> {candidate_quality.get('average_line_length', 0.0)}"
            )
        preview.append("override_applied" if override_applied else "baseline_retained_after_probe")
        return preview

    def _maybe_recommend_routing(
        self,
        source: AcquiredSource,
        *,
        preflight_inspection: InspectionReport,
        llm_requested: bool,
        parser_hint: str | None,
    ) -> LlmAdvice:
        if not llm_requested or not self._settings.enable_llm_routing or self._llm is None:
            return LlmAdvice(used=False)

        same_format_candidates = executable_candidates_for_format(source.document_format)
        if len(same_format_candidates) <= 1:
            return LlmAdvice(used=False)

        feature_summary = (
            f"page_count={preflight_inspection.common.page_count} "
            f"sheet_count={preflight_inspection.common.sheet_count} "
            f"complexity_score={preflight_inspection.common.complexity_score}"
        )
        prompt = (
            f"Document format: {source.document_format.value}\n"
            f"Source name: {source.source_name}\n"
            f"Parser hint: {parser_hint or 'none'}\n"
            f"Feature summary: {feature_summary}\n"
            f"Executable candidates: {', '.join(same_format_candidates) or 'none'}\n"
            "Choose the best parser id and return compact JSON with keys recommendation and rationale. "
            "Do not ask for the full document text."
        )
        return self._llm.recommend_routing(prompt=prompt[: self._settings.llm_max_input_chars])

    def _resolve_parser_override(
        self,
        document_format: DocumentFormat,
        *,
        parser_hint: str | None,
        routing_advice: LlmAdvice,
    ) -> str | None:
        candidates = executable_candidates_for_format(document_format)
        if parser_hint and parser_hint in candidates:
            return parser_hint
        if routing_advice.used and routing_advice.recommendation and routing_advice.recommendation in candidates:
            return routing_advice.recommendation
        return None

    def _maybe_recommend_repair(
        self,
        source: AcquiredSource,
        result: PipelineResult,
        *,
        repair_candidates: list[dict[str, object]],
        llm_requested: bool,
    ) -> tuple[list[dict[str, object]], dict[str, object] | None]:
        if not llm_requested or self._llm is None or not repair_candidates:
            return [], None

        issue_lookup = {issue.issue_id: issue for issue in result.validation.issues}
        targets = [
            candidate
            for candidate in repair_candidates
            if str(candidate.get("repair_type")) == "formula_reconstruction"
            and bool(candidate.get("llm_recommended", True))
            and str(
                issue_lookup.get(str(candidate.get("issue_id")), None).details.get("corruption_class", "")
                if issue_lookup.get(str(candidate.get("issue_id")), None) is not None
                else ""
            ) in FORMULA_REPAIR_CLASSES
        ]
        if not targets:
            return [], None

        markdown_text = str(result.metadata.get("markdown", ""))
        prompt_items = []
        for candidate in targets:
            line_number = candidate.get("markdown_line_number")
            context_window = self._markdown_context(markdown_text, line_number if isinstance(line_number, int) else None)
            source_text = str(candidate.get("source_text", ""))
            source_span = str(candidate.get("source_span")) if candidate.get("source_span") is not None else None
            prompt_items.append(
                {
                    "issue_id": candidate.get("issue_id"),
                    "block_ref": candidate.get("block_ref"),
                    "location_hint": candidate.get("location_hint"),
                    "markdown_line_number": line_number,
                    "source_excerpt": self._excerpt_around_focus(source_text, focus_text=source_span, max_chars=240),
                    "source_span": source_span,
                    "deterministic_candidate_text": self._excerpt_around_focus(
                        str(candidate.get("candidate_text", "")),
                        focus_text=None,
                        max_chars=240,
                    ),
                    "deterministic_normalized_math": candidate.get("normalized_math"),
                    "context": self._compact_markdown_context(context_window),
                }
            )

        batched_prompt_items = self._batch_repair_prompt_items(prompt_items)
        batch_records: list[dict[str, object]] = []
        for batch_index, batch_items in enumerate(batched_prompt_items):
            batch_records.extend(
                self._execute_repair_batch(
                    document_format=source.document_format.value,
                    parser_id=result.parser_id or "unknown",
                    targets=targets,
                    batch_items=batch_items,
                    batch_label=str(batch_index + 1),
                )
            )

        merged_repairs: list[dict[str, object]] = []
        llm_candidates: list[dict[str, object]] = []
        errors: list[str] = []
        for record_item in batch_records:
            llm_candidates.extend(
                candidate for candidate in record_item.get("generated_candidates", []) if isinstance(candidate, dict)
            )
            repairs = record_item.get("response", {}).get("repairs", []) if isinstance(record_item.get("response"), dict) else []
            if isinstance(repairs, list):
                merged_repairs.extend(repair for repair in repairs if isinstance(repair, dict))
            if record_item.get("error"):
                errors.append(f"batch {record_item.get('batch_label')}: {record_item['error']}")

        record = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "document_format": source.document_format.value,
            "parser_id": result.parser_id or "unknown",
            "batch_count": len(batch_records),
            "max_output_tokens": max((int(item.get("max_output_tokens", 0)) for item in batch_records), default=0),
            "targets": prompt_items,
            "batches": batch_records,
            "response": {"repairs": merged_repairs} if merged_repairs else None,
            "error": "; ".join(errors) if errors else None,
            "generated_candidates": llm_candidates,
        }
        return llm_candidates, record

    def _execute_repair_batch(
        self,
        *,
        document_format: str,
        parser_id: str,
        targets: list[dict[str, object]],
        batch_items: list[dict[str, object]],
        batch_label: str,
    ) -> list[dict[str, object]]:
        prompt = self._build_repair_prompt(
            document_format=document_format,
            parser_id=parser_id,
            prompt_items=batch_items,
        )
        repair_max_output_tokens = min(
            max(self._settings.llm_max_output_tokens, 256 + (len(batch_items) * 120)),
            1024,
        )
        advice = self._llm.recommend_repair(
            prompt=prompt[: self._settings.llm_max_input_chars],
            max_output_tokens=repair_max_output_tokens,
        )
        if advice.error and len(batch_items) > 1:
            midpoint = max(len(batch_items) // 2, 1)
            left = self._execute_repair_batch(
                document_format=document_format,
                parser_id=parser_id,
                targets=targets,
                batch_items=batch_items[:midpoint],
                batch_label=f"{batch_label}.1",
            )
            right = self._execute_repair_batch(
                document_format=document_format,
                parser_id=parser_id,
                targets=targets,
                batch_items=batch_items[midpoint:],
                batch_label=f"{batch_label}.2",
            )
            return left + right

        batch_candidates = self._build_llm_repair_candidates(targets, advice=advice)
        return [
            {
                "batch_label": batch_label,
                "target_count": len(batch_items),
                "max_output_tokens": repair_max_output_tokens,
                "targets": batch_items,
                "response": advice.raw,
                "error": advice.error,
                "generated_candidates": batch_candidates,
            }
        ]

    def _build_repair_prompt(
        self,
        *,
        document_format: str,
        parser_id: str,
        prompt_items: list[dict[str, object]],
    ) -> str:
        return (
            f"Document format: {document_format}\n"
            f"Selected parser: {parser_id}\n"
            "You are reconstructing broken actuarial or mathematical notation from parsed markdown.\n"
            "Return JSON only with this shape:\n"
            '{"repairs":[{"issue_id":"...","candidate_text":"...","normalized_math":"...","confidence":0.0,"reason":"...","uncertain":true}]}\n'
            "Prefer one repair object per target when you have enough evidence.\n"
            "Prefer minimal reconstruction. Preserve surrounding Korean text. Do not invent values not supported by the source.\n"
            "Use the deterministic candidate as a baseline, but improve it if the notation is obviously incomplete or malformed.\n"
            f"Repair targets:\n{json.dumps(prompt_items, ensure_ascii=False)}"
        )

    def _batch_repair_prompt_items(self, prompt_items: list[dict[str, object]]) -> list[list[dict[str, object]]]:
        if not prompt_items:
            return []
        batches: list[list[dict[str, object]]] = []
        current_batch: list[dict[str, object]] = []
        current_chars = 0
        max_chars = max(int(self._settings.llm_max_input_chars * 0.7), 1200)
        for item in prompt_items:
            item_chars = len(json.dumps(item, ensure_ascii=False))
            if current_batch and (len(current_batch) >= 8 or current_chars + item_chars > max_chars):
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
            current_batch.append(item)
            current_chars += item_chars
        if current_batch:
            batches.append(current_batch)
        return batches

    def _build_repair_candidates(self, result: PipelineResult) -> list[dict[str, object]]:
        line_lookup = self._issue_markdown_line_lookup(result)
        candidates: list[dict[str, object]] = []
        for item in result.metadata.get("repair_candidates", []):
            if not isinstance(item, dict):
                continue
            candidate = dict(item)
            issue_id = str(candidate.get("issue_id", ""))
            line_number = line_lookup.get(issue_id)
            candidate["markdown_line_number"] = line_number
            patch = candidate.get("patch_proposal")
            if isinstance(patch, dict):
                hydrated_patch = dict(patch)
                hydrated_patch["markdown_line_number"] = line_number
                candidate["patch_proposal"] = hydrated_patch
            elif candidate.get("candidate_text"):
                candidate["patch_proposal"] = {
                    "action": "replace_text",
                    "target_text": str(candidate.get("source_text", "")),
                    "replacement_text": str(candidate.get("candidate_text", "")),
                    "block_ref": candidate.get("block_ref"),
                    "location_hint": candidate.get("location_hint"),
                    "markdown_line_number": line_number,
                    "confidence": float(candidate.get("confidence", 0.0)),
                    "rationale": str(candidate.get("rationale", "")),
                    "uncertain": True,
                }
            candidates.append(candidate)
        return candidates

    def _build_llm_repair_candidates(
        self,
        base_candidates: list[dict[str, object]],
        *,
        advice: LlmAdvice,
    ) -> list[dict[str, object]]:
        if not advice.used or not advice.raw:
            return []

        repairs = advice.raw.get("repairs", [])
        if not isinstance(repairs, list):
            return []

        base_by_issue = {str(item.get("issue_id", "")): item for item in base_candidates}
        llm_candidates: list[dict[str, object]] = []
        for repair in repairs:
            if not isinstance(repair, dict):
                continue
            issue_id = str(repair.get("issue_id", ""))
            base = base_by_issue.get(issue_id)
            if base is None:
                continue
            candidate_text = repair.get("candidate_text")
            if not isinstance(candidate_text, str) or not candidate_text.strip():
                continue
            confidence = self._coerce_confidence(repair.get("confidence"), fallback=float(base.get("confidence", 0.0)))
            reason = str(repair.get("reason", "LLM reconstruction proposed a reviewable replacement."))
            uncertain = bool(repair.get("uncertain", confidence < 0.85))
            llm_candidates.append(
                {
                    "issue_id": issue_id,
                    "repair_type": str(base.get("repair_type", "formula_reconstruction")),
                    "strategy": "llm_formula_reconstruction",
                    "origin": "llm",
                    "source_text": str(base.get("source_text", "")),
                    "source_span": str(base.get("source_span")) if base.get("source_span") is not None else None,
                    "candidate_text": candidate_text.strip(),
                    "normalized_math": str(repair.get("normalized_math")).strip()
                    if repair.get("normalized_math") is not None
                    else None,
                    "confidence": confidence,
                    "rationale": reason,
                    "requires_review": True,
                    "llm_recommended": False,
                    "block_ref": str(base.get("block_ref")) if base.get("block_ref") is not None else None,
                    "markdown_line_number": base.get("markdown_line_number"),
                    "location_hint": str(base.get("location_hint")) if base.get("location_hint") is not None else None,
                    "severity": str(base.get("severity", "warning")),
                    "patch_proposal": {
                        "action": "replace_text",
                        "target_text": str(base.get("source_text", "")),
                        "replacement_text": candidate_text.strip(),
                        "block_ref": base.get("block_ref"),
                        "location_hint": base.get("location_hint"),
                        "markdown_line_number": base.get("markdown_line_number"),
                        "confidence": confidence,
                        "rationale": reason,
                        "uncertain": uncertain,
                    },
                }
            )
        return llm_candidates

    def _issue_markdown_line_lookup(self, result: PipelineResult) -> dict[str, int]:
        line_lookup: dict[str, int] = {}
        raw_line_map = result.metadata.get("markdown_line_map", [])
        if not isinstance(raw_line_map, list):
            return line_lookup

        line_map = [item for item in raw_line_map if isinstance(item, dict)]
        for issue in result.validation.issues:
            refs = self._issue_refs(issue)
            if not refs:
                continue
            for item in line_map:
                item_refs = item.get("refs", [])
                if not isinstance(item_refs, list):
                    continue
                if any(ref in item_refs for ref in refs):
                    line_lookup[issue.issue_id] = int(item.get("line_number", 0))
                    break
        return line_lookup

    def _issue_refs(self, issue: object) -> list[str]:
        refs: list[str] = []
        location = getattr(issue, "location", None)
        if location is not None:
            if getattr(location, "block_ref", None):
                refs.append(str(location.block_ref))
            if getattr(location, "line_hint", None):
                refs.append(str(location.line_hint))
        for excerpt in getattr(issue, "excerpts", ()):
            if getattr(excerpt, "location_hint", None):
                refs.append(str(excerpt.location_hint))
        return refs

    def _markdown_context(self, markdown: str, line_number: int | None) -> list[dict[str, object]]:
        if not markdown or line_number is None or line_number <= 0:
            return []
        lines = markdown.splitlines()
        start = max(1, line_number - 1)
        end = min(len(lines), line_number + 1)
        return [{"line_number": index, "text": lines[index - 1]} for index in range(start, end + 1)]

    def _compact_markdown_context(self, context_window: list[dict[str, object]]) -> list[dict[str, object]]:
        compact: list[dict[str, object]] = []
        for item in context_window[:3]:
            if not isinstance(item, dict):
                continue
            compact.append(
                {
                    "line_number": int(item.get("line_number", 0)),
                    "text": self._excerpt_around_focus(str(item.get("text", "")), focus_text=None, max_chars=180),
                }
            )
        return compact

    def _excerpt_around_focus(self, text: str, *, focus_text: str | None, max_chars: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_chars:
            return normalized
        if focus_text:
            focus_index = normalized.find(focus_text)
            if focus_index >= 0:
                half_window = max(20, (max_chars - len(focus_text)) // 2)
                start = max(0, focus_index - half_window)
                end = min(len(normalized), focus_index + len(focus_text) + half_window)
                excerpt = normalized[start:end]
                if start > 0:
                    excerpt = f"...{excerpt}"
                if end < len(normalized):
                    excerpt = f"{excerpt}..."
                return excerpt
        return f"{normalized[: max_chars - 3]}..."

    def _coerce_confidence(self, value: object, *, fallback: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = fallback
        return max(0.0, min(confidence, 1.0))

    def _persist_repair_outputs(
        self,
        result: PipelineResult,
        *,
        repair_candidates: list[dict[str, object]],
        llm_repair_record: dict[str, object] | None,
        markdown_line_map: list[dict[str, object]] | None = None,
        suggested_resolved_markdown: str | None = None,
        suggested_resolved_patches: list[dict[str, object]] | None = None,
        final_resolved_markdown: str | None = None,
        final_resolved_patches: list[dict[str, object]] | None = None,
        resolution_summary: dict[str, object] | None = None,
        downstream_handoff: dict[str, object] | None = None,
        evaluation: dict[str, object] | None = None,
    ) -> dict[str, str]:
        export_dir = result.metadata.get("export_dir")
        if not isinstance(export_dir, str) or not export_dir:
            return {}

        run_dir = Path(export_dir)
        if not run_dir.exists():
            return {}

        persisted: dict[str, str] = {}
        repair_candidates_path = run_dir / "repair_candidates.json"
        repair_candidates_path.write_text(
            json.dumps(repair_candidates, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        persisted["repair_candidates_path"] = str(repair_candidates_path)

        if markdown_line_map:
            markdown_line_map_path = run_dir / "markdown_line_map.json"
            markdown_line_map_path.write_text(
                json.dumps(markdown_line_map, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["markdown_line_map_path"] = str(markdown_line_map_path)

        if suggested_resolved_markdown:
            resolved_markdown_path = run_dir / "suggested_resolved.md"
            resolved_markdown_path.write_text(
                suggested_resolved_markdown,
                encoding="utf-8",
            )
            persisted["suggested_resolved_markdown_path"] = str(resolved_markdown_path)

        if suggested_resolved_patches:
            resolved_patches_path = run_dir / "suggested_resolved_patches.json"
            resolved_patches_path.write_text(
                json.dumps(suggested_resolved_patches, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["suggested_resolved_patches_path"] = str(resolved_patches_path)

        if final_resolved_markdown:
            final_resolved_markdown_path = run_dir / "final_resolved.md"
            final_resolved_markdown_path.write_text(
                final_resolved_markdown,
                encoding="utf-8",
            )
            persisted["final_resolved_markdown_path"] = str(final_resolved_markdown_path)

        canonical_markdown = self._select_canonical_markdown(
            source_markdown=str(result.metadata.get("markdown", "")),
            final_resolved_markdown=final_resolved_markdown,
            downstream_handoff=downstream_handoff,
        )
        canonical_markdown_filename = self._canonical_markdown_filename(result)
        canonical_markdown_path = run_dir / canonical_markdown_filename
        canonical_markdown_path.write_text(
            canonical_markdown,
            encoding="utf-8",
        )
        persisted["canonical_markdown_path"] = str(canonical_markdown_path)
        persisted["canonical_markdown_filename"] = canonical_markdown_filename

        if final_resolved_patches:
            final_resolved_patches_path = run_dir / "final_resolved_patches.json"
            final_resolved_patches_path.write_text(
                json.dumps(final_resolved_patches, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["final_resolved_patches_path"] = str(final_resolved_patches_path)

        if resolution_summary is not None:
            resolution_summary_path = run_dir / "resolution_summary.json"
            resolution_summary_path.write_text(
                json.dumps(resolution_summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["resolution_summary_path"] = str(resolution_summary_path)

        if downstream_handoff is not None:
            downstream_handoff_path = run_dir / "downstream_handoff.json"
            downstream_handoff_path.write_text(
                json.dumps(downstream_handoff, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["downstream_handoff_path"] = str(downstream_handoff_path)

        if evaluation is not None:
            evaluation_path = run_dir / "parse_evaluation.json"
            evaluation_path.write_text(
                json.dumps(evaluation, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["parse_evaluation_path"] = str(evaluation_path)

        if llm_repair_record is not None:
            llm_repair_path = run_dir / "llm_formula_repair.json"
            llm_repair_path.write_text(
                json.dumps(llm_repair_record, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            persisted["llm_formula_repair_path"] = str(llm_repair_path)

        return persisted

    def _select_canonical_markdown(
        self,
        *,
        source_markdown: str,
        final_resolved_markdown: str | None,
        downstream_handoff: dict[str, object] | None,
    ) -> str:
        preferred_kind = str((downstream_handoff or {}).get("preferred_markdown_kind", "source"))
        if preferred_kind == "resolved" and final_resolved_markdown:
            return final_resolved_markdown
        return source_markdown

    def _canonical_markdown_filename(self, result: PipelineResult) -> str:
        source_name = str(result.metadata.get("source_name") or "document")
        return self._canonical_markdown_filename_for_source_name(source_name)

    def _build_suggested_resolved_markdown(
        self,
        *,
        markdown: str,
        repair_candidates: list[dict[str, object]],
    ) -> tuple[str | None, list[dict[str, object]]]:
        if not markdown or not repair_candidates:
            return None, []

        candidates_by_issue = self._group_patch_candidates_by_issue(repair_candidates)
        if not candidates_by_issue:
            return None, []

        lines = markdown.split("\n")
        applied_patches: list[dict[str, object]] = []
        ordered_issue_candidates = sorted(
            candidates_by_issue.values(),
            key=lambda item: (
                min(
                    (
                        int(candidate.get("markdown_line_number", 10**9))
                        if candidate.get("markdown_line_number") is not None
                        else 10**9
                    )
                    for candidate in item
                ),
                -max(float(candidate.get("confidence", 0.0)) for candidate in item),
            ),
        )
        for issue_candidates in ordered_issue_candidates:
            ranked_candidates = sorted(issue_candidates, key=self._candidate_sort_key)
            for candidate in ranked_candidates:
                patch = candidate.get("patch_proposal")
                if not isinstance(patch, dict):
                    continue
                if self._apply_patch_proposal(lines, patch):
                    applied_patch = dict(patch)
                    applied_patch["issue_id"] = str(candidate.get("issue_id", ""))
                    applied_patch["origin"] = str(candidate.get("origin", "deterministic"))
                    applied_patches.append(applied_patch)
                    break

        resolved_markdown = "\n".join(lines)
        if not applied_patches or resolved_markdown == markdown:
            return None, []
        return resolved_markdown, applied_patches

    def _maybe_run_formula_probe(
        self,
        *,
        final_resolved_markdown: str | None,
        llm_requested: bool,
        persisted_paths: dict[str, str],
    ) -> dict[str, object] | None:
        if not final_resolved_markdown or FORMULA_PLACEHOLDER not in final_resolved_markdown:
            return None
        final_resolved_path = persisted_paths.get("final_resolved_markdown_path")
        if final_resolved_path is None:
            return None
        run_dir = Path(final_resolved_path).parent
        try:
            record = run_first_formula_probe(
                run_dir,
                settings=self._settings,
                call_llm=bool(llm_requested and self._llm is not None),
            )
        except Exception as exc:
            return {"error": str(exc)}
        artifact_path = record.get("artifact_path")
        if artifact_path is not None:
            persisted_paths["first_formula_probe_path"] = str(artifact_path)
        region_image_path = record.get("region_image_path")
        if region_image_path is not None:
            persisted_paths["first_formula_probe_region_image_path"] = str(region_image_path)
        return record

    def _group_patch_candidates_by_issue(
        self,
        repair_candidates: list[dict[str, object]],
    ) -> dict[str, list[dict[str, object]]]:
        candidates_by_issue: dict[str, list[dict[str, object]]] = defaultdict(list)
        for candidate in repair_candidates:
            patch = candidate.get("patch_proposal")
            if not isinstance(patch, dict):
                continue
            issue_id = str(candidate.get("issue_id", ""))
            if issue_id:
                candidates_by_issue[issue_id].append(candidate)
        return dict(candidates_by_issue)

    def _select_best_repair_candidates(
        self,
        repair_candidates: list[dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        selected_by_issue: dict[str, dict[str, object]] = {}
        for issue_id, candidates in self._group_patch_candidates_by_issue(repair_candidates).items():
            selected_by_issue[issue_id] = sorted(candidates, key=self._candidate_sort_key)[0]
        return selected_by_issue

    def _apply_patch_proposal(self, lines: list[str], patch: dict[str, object]) -> bool:
        line_number = patch.get("markdown_line_number")
        target_text = str(patch.get("target_text", ""))
        replacement_text = str(patch.get("replacement_text", ""))
        if not target_text or not replacement_text:
            return False
        if isinstance(line_number, int) and 1 <= line_number <= len(lines):
            current_line = lines[line_number - 1]
            if target_text in current_line:
                lines[line_number - 1] = current_line.replace(target_text, replacement_text, 1)
                return True
        joined = "\n".join(lines)
        if target_text not in joined:
            return False
        joined = joined.replace(target_text, replacement_text, 1)
        lines[:] = joined.split("\n")
        return True

    def _build_resolution_summary(
        self,
        *,
        issues: tuple[object, ...],
        repair_candidates: list[dict[str, object]],
        final_resolved_patches: list[dict[str, object]],
        llm_requested: bool,
        llm_repair_record: dict[str, object] | None = None,
    ) -> dict[str, object]:
        issue_ids = {
            str(item.get("issue_id", ""))
            for item in repair_candidates
            if str(item.get("issue_id", ""))
        }
        selected_candidate_by_issue = self._select_best_repair_candidates(repair_candidates)
        selected_patch_by_issue = {
            str(patch.get("issue_id", "")): patch
            for patch in final_resolved_patches
            if str(patch.get("issue_id", ""))
        }
        selected_issue_ids = set(selected_patch_by_issue)
        recovered_deterministic_count = sum(
            1 for patch in selected_patch_by_issue.values() if str(patch.get("origin", "deterministic")) == "deterministic"
        )
        recovered_llm_count = sum(1 for patch in selected_patch_by_issue.values() if str(patch.get("origin", "")) == "llm")
        issue_metadata = {
            issue.issue_id: str(getattr(issue, "details", {}).get("corruption_class", "") or "") for issue in issues
        }
        candidates_by_issue: dict[str, list[dict[str, object]]] = defaultdict(list)
        for item in repair_candidates:
            issue_id = str(item.get("issue_id", ""))
            if issue_id:
                candidates_by_issue[issue_id].append(item)
        llm_attempted_issue_ids = {
            str(item.get("issue_id", ""))
            for item in (llm_repair_record or {}).get("targets", [])
            if isinstance(item, dict) and str(item.get("issue_id", ""))
        }

        unresolved_by_class: Counter[str] = Counter()
        unresolved_by_reason: Counter[str] = Counter()
        issue_summaries: list[dict[str, object]] = []
        for issue_id in sorted(issue_ids):
            issue_candidates = candidates_by_issue.get(issue_id, [])
            selected_patch = selected_patch_by_issue.get(issue_id)
            selected_candidate = self._match_selected_candidate(issue_candidates, selected_patch) or selected_candidate_by_issue.get(
                issue_id
            )
            corruption_class = issue_metadata.get(issue_id) or None
            llm_attempted = issue_id in llm_attempted_issue_ids or any(
                str(item.get("origin", "")) == "llm" for item in issue_candidates
            )
            has_llm_candidate = any(str(item.get("origin", "")) == "llm" for item in issue_candidates)
            deterministic_candidates = [
                item for item in issue_candidates if str(item.get("origin", "deterministic")) == "deterministic"
            ]
            llm_recommended = any(bool(item.get("llm_recommended", True)) for item in deterministic_candidates)
            has_patch_proposal = any(isinstance(item.get("patch_proposal"), dict) for item in issue_candidates)

            unresolved_reason = None
            if selected_patch is None:
                if selected_candidate is not None:
                    unresolved_reason = "selected_patch_not_applied"
                elif llm_recommended and not llm_attempted:
                    unresolved_reason = "llm_not_requested" if not llm_requested else "llm_no_repair_generated"
                elif has_llm_candidate:
                    unresolved_reason = "llm_candidate_not_selected"
                elif llm_attempted:
                    unresolved_reason = "llm_no_repair_generated"
                elif not has_patch_proposal:
                    unresolved_reason = "no_patch_proposal"
                else:
                    unresolved_reason = "deterministic_candidate_not_selected"

            if unresolved_reason is not None:
                unresolved_by_reason[unresolved_reason] += 1
                unresolved_by_class[corruption_class or "unknown"] += 1

            candidate_decisions = self._build_issue_candidate_decisions(
                issue_candidates,
                selected_candidate=selected_candidate,
            )
            issue_summaries.append(
                {
                    "issue_id": issue_id,
                    "corruption_class": corruption_class,
                    "resolved": selected_patch is not None,
                    "selected_origin": str(selected_candidate.get("origin")) if selected_candidate is not None else None,
                    "selected_confidence": float(selected_candidate.get("confidence", 0.0))
                    if selected_candidate is not None
                    else None,
                    "selection_reason": self._describe_selection_reason(
                        issue_candidates,
                        selected_candidate=selected_candidate,
                    ),
                    "llm_requested": llm_requested,
                    "llm_attempted": llm_attempted,
                    "unresolved_reason": unresolved_reason,
                    "candidate_decisions": candidate_decisions,
                }
            )

        return {
            "repair_issue_count": len(issue_ids),
            "resolved_issue_count": len(selected_issue_ids),
            "recovered_deterministic_count": recovered_deterministic_count,
            "recovered_llm_count": recovered_llm_count,
            "unresolved_repair_issue_count": sum(unresolved_by_reason.values()),
            "unresolved_by_class": dict(unresolved_by_class),
            "unresolved_by_reason": dict(unresolved_by_reason),
            "issues": issue_summaries,
        }

    def _build_issue_candidate_decisions(
        self,
        issue_candidates: list[dict[str, object]],
        *,
        selected_candidate: dict[str, object] | None,
    ) -> list[dict[str, object]]:
        decisions: list[dict[str, object]] = []
        selected_rank = self._candidate_rank(selected_candidate) if selected_candidate is not None else None
        for candidate_index, candidate in enumerate(issue_candidates):
            patch_available = isinstance(candidate.get("patch_proposal"), dict)
            selected = selected_candidate is candidate
            rejected_reason = None
            if not selected:
                if not patch_available:
                    rejected_reason = "no_patch_proposal"
                elif selected_candidate is None or selected_rank is None:
                    rejected_reason = "no_issue_winner"
                else:
                    candidate_rank = self._candidate_rank(candidate)
                    if candidate_rank > selected_rank:
                        rejected_reason = "patch_not_applicable"
                    elif candidate_rank[0] < selected_rank[0]:
                        rejected_reason = "lower_priority_origin"
                    elif candidate_rank[1] < selected_rank[1]:
                        rejected_reason = "lower_confidence"
                    else:
                        rejected_reason = "tie_not_selected"

            decisions.append(
                {
                    "candidate_index": candidate_index,
                    "origin": str(candidate.get("origin", "deterministic")),
                    "strategy": str(candidate.get("strategy")) if candidate.get("strategy") is not None else None,
                    "confidence": float(candidate.get("confidence", 0.0)),
                    "selected": selected,
                    "patch_available": patch_available,
                    "rejected_reason": rejected_reason,
                }
            )
        return decisions

    def _describe_selection_reason(
        self,
        issue_candidates: list[dict[str, object]],
        *,
        selected_candidate: dict[str, object] | None,
    ) -> str | None:
        if selected_candidate is None:
            return None
        ranked_candidates = [item for item in issue_candidates if isinstance(item.get("patch_proposal"), dict)]
        if len(ranked_candidates) <= 1:
            return "only_patch_proposal"

        selected_origin = str(selected_candidate.get("origin", "deterministic"))
        other_candidates = [item for item in ranked_candidates if item is not selected_candidate]
        selected_rank = self._candidate_rank(selected_candidate)
        if any(self._candidate_rank(item) > selected_rank for item in other_candidates):
            return "best_applicable_patch"
        if selected_origin == "llm" and any(str(item.get("origin", "deterministic")) != "llm" for item in other_candidates):
            return "llm_priority"

        selected_confidence = float(selected_candidate.get("confidence", 0.0))
        if all(float(item.get("confidence", 0.0)) < selected_confidence for item in other_candidates):
            return "highest_confidence"
        return "highest_rank"

    def _match_selected_candidate(
        self,
        issue_candidates: list[dict[str, object]],
        selected_patch: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if selected_patch is None:
            return None
        selected_origin = str(selected_patch.get("origin", "deterministic"))
        selected_target_text = str(selected_patch.get("target_text", ""))
        selected_replacement_text = str(selected_patch.get("replacement_text", ""))
        for candidate in issue_candidates:
            patch = candidate.get("patch_proposal")
            if not isinstance(patch, dict):
                continue
            if (
                str(candidate.get("origin", "deterministic")) == selected_origin
                and str(patch.get("target_text", "")) == selected_target_text
                and str(patch.get("replacement_text", "")) == selected_replacement_text
            ):
                return candidate
        return None

    def _candidate_rank(self, candidate: dict[str, object]) -> tuple[int, float]:
        origin = str(candidate.get("origin", "deterministic"))
        confidence = float(candidate.get("confidence", 0.0))
        return (1 if origin == "llm" else 0, confidence)

    def _candidate_sort_key(self, candidate: dict[str, object]) -> tuple[int, float]:
        origin_rank, confidence = self._candidate_rank(candidate)
        return (-origin_rank, -confidence)

    def _build_downstream_handoff(
        self,
        *,
        handoff_decision: str,
        markdown: str,
        final_resolved_markdown: str | None,
        final_resolved_patches: list[dict[str, object]],
        repair_candidates: list[dict[str, object]],
        resolution_summary: dict[str, int],
    ) -> dict[str, object]:
        has_llm_candidate = any(str(item.get("origin", "")) == "llm" for item in repair_candidates)
        has_resolved = bool(final_resolved_markdown)
        unresolved_repair_issue_count = int(resolution_summary.get("unresolved_repair_issue_count", 0))
        has_unresolved_repair = unresolved_repair_issue_count > 0
        placeholder_count = (
            str(final_resolved_markdown).count(FORMULA_PLACEHOLDER)
            if final_resolved_markdown is not None
            else 0
        )
        has_placeholder_residue = placeholder_count > 0
        uncertain_patch_exists = any(bool(item.get("uncertain", True)) for item in final_resolved_patches if isinstance(item, dict))
        if handoff_decision == "accept" and not has_resolved:
            return {
                "policy": "source_only",
                "preferred_markdown_kind": "source",
                "review_required": False,
                "source_markdown_available": bool(markdown),
                "suggested_resolved_available": False,
                "final_resolved_available": False,
                "rationale": [
                    "No blocking repair proposals exist, so downstream should use the source-faithful markdown.",
                ],
            }
        if has_resolved:
            rationale = [
                "A resolved markdown artifact was assembled from the highest-ranked repair patches.",
                "Downstream should prefer the resolved markdown while preserving the source markdown for audit and fallback.",
            ]
            if has_unresolved_repair:
                rationale.append(
                    f"Some repairable issues remain unresolved after enabled recovery steps: {unresolved_repair_issue_count}."
                )
            if has_llm_candidate:
                rationale.append("At least one LLM-generated repair was merged into the final resolved markdown candidate.")
            if has_placeholder_residue:
                rationale.append(
                    f"The resolved markdown still contains undecoded formula placeholders: {placeholder_count}."
                )
                rationale.append(
                    "Downstream should keep source markdown as canonical input until placeholder residues are removed or explicitly accepted."
                )
                return {
                    "policy": "dual_track_review",
                    "preferred_markdown_kind": "source",
                    "review_required": True,
                    "source_markdown_available": bool(markdown),
                    "suggested_resolved_available": True,
                    "final_resolved_available": True,
                    "remaining_placeholder_count": placeholder_count,
                    "rationale": rationale,
                }
            return {
                "policy": "resolved_preferred" if not has_unresolved_repair else "resolved_with_fallback",
                "preferred_markdown_kind": "resolved",
                "review_required": has_unresolved_repair or uncertain_patch_exists,
                "source_markdown_available": bool(markdown),
                "suggested_resolved_available": True,
                "final_resolved_available": True,
                "remaining_placeholder_count": placeholder_count,
                "rationale": rationale,
            }

        rationale = [
            "Validation reported repairable corruption, but no resolved markdown artifact could be assembled.",
            "Downstream should keep the source markdown as canonical input until more recovery is possible.",
        ]
        if has_llm_candidate:
            rationale.append("At least one LLM-generated formula reconstruction was produced, but it did not yield a complete resolved markdown artifact.")
        return {
            "policy": "dual_track_review",
            "preferred_markdown_kind": "source",
            "review_required": True,
            "source_markdown_available": bool(markdown),
            "suggested_resolved_available": has_resolved,
            "final_resolved_available": False,
            "remaining_placeholder_count": 0,
            "rationale": rationale,
        }

    def _build_parse_evaluation(
        self,
        *,
        issue_count: int,
        repair_candidates: list[dict[str, object]],
        final_resolved_patches: list[dict[str, object]],
        downstream_handoff: dict[str, object],
        resolution_summary: dict[str, int],
    ) -> dict[str, object]:
        deterministic_count = sum(1 for item in repair_candidates if str(item.get("origin", "")) == "deterministic")
        llm_count = sum(1 for item in repair_candidates if str(item.get("origin", "")) == "llm")
        llm_recommended_count = sum(
            1
            for item in repair_candidates
            if str(item.get("origin", "")) == "deterministic" and bool(item.get("llm_recommended", True))
        )
        strong_deterministic_count = sum(
            1
            for item in repair_candidates
            if str(item.get("origin", "")) == "deterministic" and not bool(item.get("llm_recommended", True))
        )
        review_required = bool(downstream_handoff.get("review_required", False))
        recovered_deterministic_count = int(resolution_summary.get("recovered_deterministic_count", 0))
        recovered_llm_count = int(resolution_summary.get("recovered_llm_count", 0))
        unresolved_repair_issue_count = int(resolution_summary.get("unresolved_repair_issue_count", 0))
        preferred_markdown_kind = str(downstream_handoff.get("preferred_markdown_kind", "source"))
        placeholder_residue_count = int(downstream_handoff.get("remaining_placeholder_count", 0))
        score = 100
        score -= min(issue_count * 12, 36)
        score -= min(sum(1 for item in repair_candidates if bool(item.get("requires_review", True))) * 5, 20)
        if llm_count > 0:
            score += 8
        if strong_deterministic_count > 0:
            score += min(strong_deterministic_count * 4, 8)
        if llm_recommended_count > 0:
            score -= min(llm_recommended_count * 3, 9)
        if final_resolved_patches:
            score += 6
        if preferred_markdown_kind == "resolved":
            score += 8
        if unresolved_repair_issue_count > 0:
            score -= min(unresolved_repair_issue_count * 4, 16)
        if placeholder_residue_count:
            score -= min(placeholder_residue_count * 2, 20)
        score = max(0, min(score, 100))

        if score >= 85 and preferred_markdown_kind == "resolved" and not review_required:
            label = "ready"
            next_step = "Proceed with final resolved markdown as canonical downstream input."
        elif score >= 85 and not review_required:
            label = "ready"
            next_step = "Proceed with source markdown as canonical downstream input."
        elif score >= 65:
            label = "reviewable"
            next_step = (
                "Use final resolved markdown for downstream and keep source markdown for audit."
                if preferred_markdown_kind == "resolved"
                else "Use source markdown for downstream and inspect suggested repairs before canonicalization."
            )
        else:
            label = "fragile"
            next_step = "Inspect repair candidates before trusting the parse for downstream indexing."

        rationale = [
            f"Detected issues: {issue_count}",
            f"Repair candidates: {len(repair_candidates)}",
        ]
        if strong_deterministic_count:
            rationale.append(f"High-structure deterministic candidates: {strong_deterministic_count}")
        if llm_recommended_count:
            rationale.append(f"Deterministic candidates still recommending LLM review: {llm_recommended_count}")
        if llm_count:
            rationale.append(f"LLM reconstructions generated: {llm_count}")
        if final_resolved_patches:
            rationale.append(f"Suggested resolved patches applied: {len(final_resolved_patches)}")
        if recovered_deterministic_count:
            rationale.append(f"Deterministic repairs carried into final output: {recovered_deterministic_count}")
        if recovered_llm_count:
            rationale.append(f"LLM repairs carried into final output: {recovered_llm_count}")
        if unresolved_repair_issue_count:
            rationale.append(f"Repairable issues still unresolved after all enabled recovery: {unresolved_repair_issue_count}")
        if placeholder_residue_count:
            rationale.append(f"Formula placeholders still remain in final resolved markdown: {placeholder_residue_count}")
        unresolved_by_class = resolution_summary.get("unresolved_by_class", {})
        if isinstance(unresolved_by_class, dict) and unresolved_by_class:
            formatted = ", ".join(f"{key}={value}" for key, value in sorted(unresolved_by_class.items()))
            rationale.append(f"Unresolved repair classes: {formatted}")
        unresolved_by_reason = resolution_summary.get("unresolved_by_reason", {})
        if isinstance(unresolved_by_reason, dict) and unresolved_by_reason:
            formatted = ", ".join(f"{key}={value}" for key, value in sorted(unresolved_by_reason.items()))
            rationale.append(f"Unresolved repair reasons: {formatted}")

        return {
            "readiness_score": score,
            "readiness_label": label,
            "issue_count": issue_count,
            "repair_candidate_count": len(repair_candidates),
            "deterministic_candidate_count": deterministic_count,
            "llm_candidate_count": llm_count,
            "suggested_patch_count": len(final_resolved_patches),
            "recovered_deterministic_count": recovered_deterministic_count,
            "recovered_llm_count": recovered_llm_count,
            "unresolved_repair_issue_count": unresolved_repair_issue_count,
            "review_required": review_required,
            "recommended_next_step": next_step,
            "rationale": rationale,
        }

    def _to_response(
        self,
        *,
        source: AcquiredSource,
        result: PipelineResult,
        llm_requested: bool,
        llm_used: bool,
        routing_advice: LlmAdvice,
        routing_probe: dict[str, object] | None,
        llm_repair_record: dict[str, object] | None,
        notes: list[str],
        repair_candidates: list[dict[str, object]],
        suggested_resolved_markdown: str | None,
        suggested_resolved_patches: list[dict[str, object]],
        final_resolved_markdown: str | None,
        final_resolved_patches: list[dict[str, object]],
        resolution_summary: dict[str, object],
        downstream_handoff: dict[str, object],
        evaluation: dict[str, object],
        formula_probe_record: dict[str, object] | None,
    ) -> ParseResponse:
        source_summary = SourceSummary(
            kind=source.source_kind,
            name=source.source_name,
            uri=source.uri,
            document_format=source.document_format,
            size_bytes=source.size_bytes,
            content_type=source.content_type,
        )
        markdown = str(result.metadata.get("markdown", ""))
        markdown_line_map = [
            MarkdownLineMapEntryResponse(
                line_number=int(item.get("line_number", 0)),
                text=str(item.get("text", "")),
                refs=[str(ref) for ref in item.get("refs", [])],
                page_number=int(item.get("page_number")) if item.get("page_number") is not None else None,
            )
            for item in result.metadata.get("markdown_line_map", [])
            if isinstance(item, dict)
        ]
        repair_candidates = [
            RepairCandidateResponse(
                issue_id=str(item.get("issue_id", "")),
                repair_type=str(item.get("repair_type", "")),
                strategy=str(item.get("strategy", "")),
                origin=str(item.get("origin", "deterministic")),
                source_text=str(item.get("source_text", "")),
                source_span=str(item.get("source_span")) if item.get("source_span") is not None else None,
                candidate_text=str(item.get("candidate_text")) if item.get("candidate_text") is not None else None,
                normalized_math=str(item.get("normalized_math")) if item.get("normalized_math") is not None else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", "")),
                requires_review=bool(item.get("requires_review", True)),
                llm_recommended=bool(item.get("llm_recommended", True)),
                block_ref=str(item.get("block_ref")) if item.get("block_ref") is not None else None,
                markdown_line_number=int(item.get("markdown_line_number"))
                if item.get("markdown_line_number") is not None
                else None,
                location_hint=str(item.get("location_hint")) if item.get("location_hint") is not None else None,
                severity=str(item.get("severity", "warning")),
                patch_proposal=item.get("patch_proposal"),
            )
            for item in repair_candidates
            if isinstance(item, dict)
        ]
        suggested_patch_responses = [
            RepairPatchProposalResponse(
                action=str(item.get("action", "")),
                target_text=str(item.get("target_text", "")),
                replacement_text=str(item.get("replacement_text", "")),
                origin=str(item.get("origin")) if item.get("origin") is not None else None,
                block_ref=str(item.get("block_ref")) if item.get("block_ref") is not None else None,
                location_hint=str(item.get("location_hint")) if item.get("location_hint") is not None else None,
                markdown_line_number=int(item.get("markdown_line_number"))
                if item.get("markdown_line_number") is not None
                else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", "")),
                uncertain=bool(item.get("uncertain", True)),
            )
            for item in suggested_resolved_patches
            if isinstance(item, dict)
        ]
        artifacts = [
            ArtifactResponse(
                kind=artifact.kind,
                label=artifact.label,
                path=str(artifact.path) if artifact.path else None,
                metadata=artifact.metadata,
            )
            for artifact in (
                result.artifacts.inspection,
                result.artifacts.routing,
                result.artifacts.parser_output,
                result.artifacts.normalized_ir,
                result.artifacts.validation,
                result.artifacts.markdown,
                result.artifacts.metadata,
                result.artifacts.trace,
            )
            if artifact is not None
        ]
        return ParseResponse(
            request_id=result.run_id or str(uuid4()),
            source=source_summary,
            routing=routing_from_domain(result.route),
            handoff=handoff_from_domain(result.handoff),
            trace={
                "trace_id": result.trace.trace_id,
                "status": result.trace.status,
                "source": source_summary,
                "events": [trace_event_from_domain(event) for event in result.trace.events],
                "warnings": list(result.trace.warnings),
                "metadata": result.trace.metadata,
            },
            issues=[issue_from_domain(issue.to_snapshot()) for issue in result.validation.issues],
            artifacts=artifacts,
            markdown=markdown,
            markdown_line_map=markdown_line_map,
            repair_candidates=repair_candidates,
            suggested_resolved_markdown=suggested_resolved_markdown,
            suggested_resolved_patches=suggested_patch_responses,
            final_resolved_markdown=final_resolved_markdown,
            final_resolved_patches=[
                RepairPatchProposalResponse(
                    action=str(item.get("action", "")),
                    target_text=str(item.get("target_text", "")),
                    replacement_text=str(item.get("replacement_text", "")),
                    origin=str(item.get("origin")) if item.get("origin") is not None else None,
                    block_ref=str(item.get("block_ref")) if item.get("block_ref") is not None else None,
                    location_hint=str(item.get("location_hint")) if item.get("location_hint") is not None else None,
                    markdown_line_number=int(item.get("markdown_line_number"))
                    if item.get("markdown_line_number") is not None
                    else None,
                    confidence=float(item.get("confidence", 0.0)),
                    rationale=str(item.get("rationale", "")),
                    uncertain=bool(item.get("uncertain", True)),
                )
                for item in final_resolved_patches
                if isinstance(item, dict)
            ],
            resolution_summary=ResolutionSummaryResponse(
                repair_issue_count=int(resolution_summary.get("repair_issue_count", 0)),
                resolved_issue_count=int(resolution_summary.get("resolved_issue_count", 0)),
                recovered_deterministic_count=int(resolution_summary.get("recovered_deterministic_count", 0)),
                recovered_llm_count=int(resolution_summary.get("recovered_llm_count", 0)),
                unresolved_repair_issue_count=int(resolution_summary.get("unresolved_repair_issue_count", 0)),
                unresolved_by_class={
                    str(key): int(value)
                    for key, value in dict(resolution_summary.get("unresolved_by_class", {})).items()
                },
                unresolved_by_reason={
                    str(key): int(value)
                    for key, value in dict(resolution_summary.get("unresolved_by_reason", {})).items()
                },
                issues=[
                    ResolutionIssueDetailResponse(
                        issue_id=str(item.get("issue_id", "")),
                        corruption_class=str(item.get("corruption_class"))
                        if item.get("corruption_class") is not None
                        else None,
                        resolved=bool(item.get("resolved", False)),
                        selected_origin=str(item.get("selected_origin"))
                        if item.get("selected_origin") is not None
                        else None,
                        selected_confidence=float(item.get("selected_confidence"))
                        if item.get("selected_confidence") is not None
                        else None,
                        selection_reason=str(item.get("selection_reason"))
                        if item.get("selection_reason") is not None
                        else None,
                        llm_requested=bool(item.get("llm_requested", False)),
                        llm_attempted=bool(item.get("llm_attempted", False)),
                        unresolved_reason=str(item.get("unresolved_reason"))
                        if item.get("unresolved_reason") is not None
                        else None,
                        candidate_decisions=[
                            ResolutionCandidateDecisionResponse(
                                candidate_index=int(decision.get("candidate_index", 0)),
                                origin=str(decision.get("origin", "deterministic")),
                                strategy=str(decision.get("strategy"))
                                if decision.get("strategy") is not None
                                else None,
                                confidence=float(decision.get("confidence", 0.0)),
                                selected=bool(decision.get("selected", False)),
                                patch_available=bool(decision.get("patch_available", False)),
                                rejected_reason=str(decision.get("rejected_reason"))
                                if decision.get("rejected_reason") is not None
                                else None,
                            )
                            for decision in item.get("candidate_decisions", [])
                            if isinstance(decision, dict)
                        ],
                    )
                    for item in resolution_summary.get("issues", [])
                    if isinstance(item, dict)
                ],
            ),
            llm_diagnostics=LlmDiagnosticsResponse(
                routing_used=bool(routing_probe is not None and routing_probe.get("override_applied")),
                routing_recommendation=routing_advice.recommendation,
                routing_baseline_parser=str(routing_probe.get("baseline_parser"))
                if routing_probe is not None and routing_probe.get("baseline_parser") is not None
                else None,
                routing_selected_parser=str(routing_probe.get("selected_parser"))
                if routing_probe is not None and routing_probe.get("selected_parser") is not None
                else None,
                routing_override_applied=bool(routing_probe is not None and routing_probe.get("override_applied")),
                routing_comparison_preview=[
                    str(item) for item in (routing_probe.get("comparison_preview", []) if routing_probe is not None else [])
                ],
                repair_attempted_issues=sum(
                    1 for item in (llm_repair_record or {}).get("targets", []) if isinstance(item, dict)
                ),
                repair_generated_candidates=sum(
                    1 for item in (llm_repair_record or {}).get("generated_candidates", []) if isinstance(item, dict)
                ),
                repair_error=str(llm_repair_record.get("error"))
                if llm_repair_record is not None and llm_repair_record.get("error") is not None
                else None,
                repair_response_available=bool(llm_repair_record is not None and llm_repair_record.get("response") is not None),
                repair_response_preview=self._build_llm_repair_response_preview(llm_repair_record),
                formula_probe_attempted=bool(formula_probe_record is not None),
                formula_probe_error=self._formula_probe_error(formula_probe_record),
                formula_probe_apply_as_patch=self._formula_probe_apply_as_patch(formula_probe_record),
                formula_probe_confidence=self._formula_probe_confidence(formula_probe_record),
                formula_probe_region_image_path=str(formula_probe_record.get("region_image_path"))
                if formula_probe_record is not None and formula_probe_record.get("region_image_path") is not None
                else None,
                formula_probe_preview=self._build_formula_probe_preview(formula_probe_record),
            ),
            downstream_handoff=DownstreamHandoffResponse(
                policy=str(downstream_handoff.get("policy", "source_only")),
                preferred_markdown_kind=str(downstream_handoff.get("preferred_markdown_kind", "source")),
                review_required=bool(downstream_handoff.get("review_required", False)),
                source_markdown_available=bool(downstream_handoff.get("source_markdown_available", True)),
                suggested_resolved_available=bool(downstream_handoff.get("suggested_resolved_available", False)),
                final_resolved_available=bool(downstream_handoff.get("final_resolved_available", False)),
                rationale=[str(item) for item in downstream_handoff.get("rationale", [])],
            ),
            evaluation=ParseEvaluationResponse(
                readiness_score=int(evaluation.get("readiness_score", 0)),
                readiness_label=str(evaluation.get("readiness_label", "fragile")),
                issue_count=int(evaluation.get("issue_count", 0)),
                repair_candidate_count=int(evaluation.get("repair_candidate_count", 0)),
                deterministic_candidate_count=int(evaluation.get("deterministic_candidate_count", 0)),
                llm_candidate_count=int(evaluation.get("llm_candidate_count", 0)),
                suggested_patch_count=int(evaluation.get("suggested_patch_count", 0)),
                recovered_deterministic_count=int(evaluation.get("recovered_deterministic_count", 0)),
                recovered_llm_count=int(evaluation.get("recovered_llm_count", 0)),
                unresolved_repair_issue_count=int(evaluation.get("unresolved_repair_issue_count", 0)),
                review_required=bool(evaluation.get("review_required", True)),
                recommended_next_step=str(evaluation.get("recommended_next_step", "")),
                rationale=[str(item) for item in evaluation.get("rationale", [])],
            ),
            llm_requested=llm_requested,
            llm_used=llm_used,
            notes=notes,
        )

    def _build_notes(
        self,
        source: AcquiredSource,
        result: PipelineResult,
        routing_advice: LlmAdvice,
        *,
        repair_candidates: list[dict[str, object]],
        llm_repair_candidates: list[dict[str, object]],
        llm_repair_record: dict[str, object] | None,
        persisted_paths: dict[str, str],
    ) -> list[str]:
        notes = [
            f"source_kind={source.source_kind.value}",
            f"parser={result.parser_id or 'none'}",
            f"handoff={result.decision.value}",
        ]
        parser_route_kind = result.handoff.metadata.get("parser_route_kind")
        if parser_route_kind:
            notes.append(f"parser_route_kind={parser_route_kind}")
        if "export_dir" in result.metadata:
            notes.append(f"export_dir={result.metadata['export_dir']}")
        if routing_advice.used and routing_advice.recommendation:
            notes.append(f"llm_routing_recommendation={routing_advice.recommendation}")
        if llm_repair_record is not None:
            target_count = sum(1 for item in llm_repair_record.get("targets", []) if isinstance(item, dict))
            generated_count = sum(1 for item in llm_repair_record.get("generated_candidates", []) if isinstance(item, dict))
            notes.append(f"llm_repair_attempted_issues={target_count}")
            notes.append(f"llm_repair_generated_candidates={generated_count}")
            if llm_repair_record.get("error"):
                notes.append(f"llm_repair_error={llm_repair_record['error']}")
        if llm_repair_candidates:
            notes.append(f"llm_formula_candidates={len(llm_repair_candidates)}")
        if repair_candidates:
            notes.append(f"repair_candidates={len(repair_candidates)}")
        for key, value in persisted_paths.items():
            notes.append(f"{key}={value}")
        if result.route and result.route.primary_parser == "unsupported":
            notes.append("no_enabled_parser_route")
        return notes

    def _build_llm_repair_response_preview(self, llm_repair_record: dict[str, object] | None) -> list[str]:
        if llm_repair_record is None:
            return []
        response = llm_repair_record.get("response")
        if not isinstance(response, dict):
            return []
        repairs = response.get("repairs")
        preview: list[str] = []
        if isinstance(repairs, list):
            preview.append(f"repairs={len(repairs)}")
            for repair in repairs[:3]:
                if not isinstance(repair, dict):
                    continue
                issue_id = str(repair.get("issue_id", "")).strip() or "unknown"
                candidate_text = str(repair.get("candidate_text", "")).strip()
                reason = str(repair.get("reason", "")).strip()
                if candidate_text:
                    preview.append(f"{issue_id}: {candidate_text[:120]}")
                elif reason:
                    preview.append(f"{issue_id}: {reason[:120]}")
        if not preview:
            preview.append("response_present_but_no_repairs")
        return preview

    def _formula_probe_error(self, formula_probe_record: dict[str, object] | None) -> str | None:
        if formula_probe_record is None:
            return None
        if formula_probe_record.get("error") is not None:
            return str(formula_probe_record.get("error"))
        llm_probe = formula_probe_record.get("llm_probe")
        if isinstance(llm_probe, dict) and llm_probe.get("error") is not None:
            return str(llm_probe.get("error"))
        return None

    def _formula_probe_apply_as_patch(self, formula_probe_record: dict[str, object] | None) -> bool | None:
        response = ((formula_probe_record or {}).get("llm_probe") or {}).get("response")
        if isinstance(response, dict) and response.get("apply_as_patch") is not None:
            return bool(response.get("apply_as_patch"))
        return None

    def _formula_probe_confidence(self, formula_probe_record: dict[str, object] | None) -> float | None:
        response = ((formula_probe_record or {}).get("llm_probe") or {}).get("response")
        if isinstance(response, dict) and response.get("confidence") is not None:
            return float(response.get("confidence"))
        return None

    def _build_formula_probe_preview(self, formula_probe_record: dict[str, object] | None) -> list[str]:
        if formula_probe_record is None:
            return []
        preview: list[str] = []
        page_match = formula_probe_record.get("page_match")
        if isinstance(page_match, dict) and page_match.get("page_number") is not None:
            preview.append(f"matched_page={page_match.get('page_number')}")
        region_match = formula_probe_record.get("region_match")
        if isinstance(region_match, dict) and region_match.get("pdf_bbox") is not None:
            preview.append(f"region_bbox={json.dumps(region_match.get('pdf_bbox'), ensure_ascii=False)}")
        llm_probe = formula_probe_record.get("llm_probe")
        if not isinstance(llm_probe, dict):
            return preview
        response = llm_probe.get("response")
        if isinstance(response, dict):
            if response.get("apply_as_patch") is not None:
                preview.append(f"apply_as_patch={bool(response.get('apply_as_patch'))}")
            if response.get("confidence") is not None:
                preview.append(f"confidence={float(response.get('confidence')):.2f}")
            if response.get("reason"):
                preview.append(f"reason={str(response.get('reason'))}")
            replacement = response.get("replacement_markdown")
            if isinstance(replacement, str) and replacement.strip():
                preview.append(f"replacement={replacement.strip().replace(chr(10), ' ')[:180]}")
            raw_text = response.get("_raw_text")
            if isinstance(raw_text, str) and raw_text.strip():
                preview.append(f"raw={raw_text[:180]}")
        return preview[:6]
