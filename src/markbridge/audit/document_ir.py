"""DocumentIR audit helpers for chunking-readiness work."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from urllib.parse import urlparse

from markbridge.api.storage import download_s3_uri_to_tempfile, parse_s3_uri
from markbridge.pipeline import PipelineRequest, PipelineResult, run_pipeline
from markbridge.shared.ir import BlockKind, DocumentFormat, DocumentIR, TableBlockIR


SUPPORTED_SUFFIXES: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".doc": DocumentFormat.DOC,
    ".hwp": DocumentFormat.HWP,
}


def run_document_ir_audit(
    *,
    inputs: list[str],
    output_dir: Path | None = None,
    include_blocks: bool = False,
    parser_hint: str | None = None,
) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for raw_input in inputs:
        downloaded_path: Path | None = None
        try:
            resolved = _resolve_input(raw_input)
            downloaded_path = resolved.get("downloaded_path")
            request = PipelineRequest(
                source_path=resolved["path"],
                document_format=resolved["document_format"],
                options={
                    "source_name": resolved["source_name"],
                    "source_uri": resolved["source_uri"],
                    **({"parser_override": parser_hint} if parser_hint else {}),
                },
            )
            result = run_pipeline(request)
            sample = summarize_pipeline_result(
                result,
                requested_input=raw_input,
                include_blocks=include_blocks,
            )
            if output_dir is not None:
                _write_audit_artifacts(
                    output_dir=output_dir,
                    sample=sample,
                    document=result.document,
                    include_blocks=include_blocks,
                )
            samples.append(sample)
        except Exception as exc:
            samples.append(
                {
                    "requested_input": raw_input,
                    "status": "failed",
                    "error": str(exc),
                }
            )
        finally:
            if downloaded_path is not None:
                downloaded_path.unlink(missing_ok=True)

    aggregate = {
        "sample_count": len(samples),
        "success_count": sum(1 for sample in samples if sample.get("status") == "ok"),
        "failed_count": sum(1 for sample in samples if sample.get("status") != "ok"),
        "samples": samples,
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "aggregate-summary.json").write_text(
            json.dumps(aggregate, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return aggregate


def summarize_pipeline_result(
    result: PipelineResult,
    *,
    requested_input: str,
    include_blocks: bool = False,
) -> dict[str, object]:
    document = result.document
    if document is None:
        return {
            "requested_input": requested_input,
            "status": "failed",
            "error": "pipeline produced no document",
        }

    block_kind_counts: dict[str, int] = {}
    blocks_with_source = 0
    blocks_with_page_source = 0
    blocks_with_sheet_source = 0
    parser_block_ref_count = 0
    heading_count = 0
    heading_level_count = 0
    table_count = 0
    table_header_depth_count = 0
    table_title_count = 0
    table_caption_count = 0
    table_page_range_count = 0

    block_summaries: list[dict[str, object]] = []
    for index, block in enumerate(document.blocks):
        block_kind_counts[block.kind.value] = block_kind_counts.get(block.kind.value, 0) + 1
        if block.source is not None:
            blocks_with_source += 1
            if block.source.page is not None:
                blocks_with_page_source += 1
            if block.source.sheet is not None:
                blocks_with_sheet_source += 1
        if block.parser_block_ref:
            parser_block_ref_count += 1
        if block.kind is BlockKind.HEADING:
            heading_count += 1
            if block.heading_level is not None:
                heading_level_count += 1
        if isinstance(block, TableBlockIR):
            table_count += 1
            if block.header_depth > 0:
                table_header_depth_count += 1
            if block.title:
                table_title_count += 1
            if block.caption:
                table_caption_count += 1
            if block.page_range is not None:
                table_page_range_count += 1
        if include_blocks:
            block_summaries.append(_summarize_block(index=index, block=block))

    summary: dict[str, object] = {
        "requested_input": requested_input,
        "status": "ok",
        "source_name": document.metadata.get("source_name"),
        "source_uri": document.metadata.get("source_uri"),
        "document_format": document.source_format.value,
        "parser_id": result.parser_id,
        "handoff_decision": result.handoff.decision.value,
        "validation_issue_count": len(result.validation.issues),
        "block_count": len(document.blocks),
        "block_kind_counts": block_kind_counts,
        "document_metadata_keys": sorted(document.metadata.keys()),
        "coverage": {
            "parser_block_ref": _coverage(parser_block_ref_count, len(document.blocks)),
            "block_source": _coverage(blocks_with_source, len(document.blocks)),
            "page_source": _coverage(blocks_with_page_source, len(document.blocks)),
            "sheet_source": _coverage(blocks_with_sheet_source, len(document.blocks)),
            "heading_level": _coverage(heading_level_count, heading_count),
            "table_header_depth": _coverage(table_header_depth_count, table_count),
            "table_title": _coverage(table_title_count, table_count),
            "table_caption": _coverage(table_caption_count, table_count),
            "table_page_range": _coverage(table_page_range_count, table_count),
        },
    }
    if include_blocks:
        summary["blocks"] = block_summaries
    return summary


def _coverage(present: int, total: int) -> dict[str, object]:
    ratio = round((present / total), 4) if total else None
    return {"present": present, "total": total, "ratio": ratio}


def _summarize_block(*, index: int, block: object) -> dict[str, object]:
    if isinstance(block, TableBlockIR):
        return {
            "index": index,
            "kind": block.kind.value,
            "parser_block_ref": block.parser_block_ref,
            "heading_level": block.heading_level,
            "source": asdict(block.source) if block.source is not None else None,
            "title": block.title,
            "caption": block.caption,
            "header_depth": block.header_depth,
            "page_range": list(block.page_range) if block.page_range is not None else None,
            "cell_count": len(block.cells),
            "metadata_keys": sorted(block.metadata.keys()),
        }
    return {
        "index": index,
        "kind": block.kind.value,
        "parser_block_ref": block.parser_block_ref,
        "heading_level": getattr(block, "heading_level", None),
        "source": asdict(block.source) if getattr(block, "source", None) is not None else None,
        "text_preview": (getattr(block, "text", None) or "")[:120],
        "metadata_keys": sorted(getattr(block, "metadata", {}).keys()),
    }


def _resolve_input(raw_input: str) -> dict[str, object]:
    if raw_input.startswith("s3://"):
        ref = parse_s3_uri(raw_input)
        suffix = Path(ref.key).suffix.lower()
        document_format = _resolve_document_format(suffix=suffix, label=ref.key)
        downloaded_path = download_s3_uri_to_tempfile(raw_input, suffix=suffix)
        return {
            "path": downloaded_path,
            "downloaded_path": downloaded_path,
            "source_name": Path(ref.key).name,
            "source_uri": raw_input,
            "document_format": document_format,
        }

    path = Path(raw_input)
    document_format = _resolve_document_format(suffix=path.suffix.lower(), label=str(path))
    return {
        "path": path,
        "downloaded_path": None,
        "source_name": path.name,
        "source_uri": None,
        "document_format": document_format,
    }


def _resolve_document_format(*, suffix: str, label: str) -> DocumentFormat:
    try:
        return SUPPORTED_SUFFIXES[suffix]
    except KeyError as exc:
        raise ValueError(f"Unsupported document format for audit input: {label}") from exc


def _write_audit_artifacts(
    *,
    output_dir: Path,
    sample: dict[str, object],
    document: DocumentIR | None,
    include_blocks: bool,
) -> None:
    source_name = str(sample.get("source_name") or urlparse(str(sample.get("requested_input") or "")).path.split("/")[-1] or "sample")
    sample_dir = output_dir / _safe_stem(source_name)
    sample_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "audit-summary.json").write_text(
        json.dumps(sample, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if include_blocks and document is not None:
        (sample_dir / "document-ir.json").write_text(
            json.dumps(asdict(document), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _safe_stem(value: str) -> str:
    sanitized = "".join(character if character.isalnum() or character in {"-", "_", "."} else "_" for character in value)
    return sanitized.strip("._") or "sample"
