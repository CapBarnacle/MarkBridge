"""One-off probe for the first unresolved formula placeholder in a parse run."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from markbridge.api.config import ApiSettings
from markbridge.api.llm import AzureLlmAdvisor
from markbridge.validators.execution import FORMULA_PLACEHOLDER


_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")


@dataclass(frozen=True, slots=True)
class PlaceholderWindow:
    line_number: int
    line_text: str
    context_before: tuple[str, ...]
    context_after: tuple[str, ...]

    @property
    def context_text(self) -> str:
        return "\n".join((*self.context_before, self.line_text, *self.context_after))


@dataclass(frozen=True, slots=True)
class LineBox:
    text: str
    normalized_text: str
    x0: float
    top: float
    x1: float
    bottom: float


def run_first_formula_probe(
    run_dir: Path,
    *,
    settings: ApiSettings,
    call_llm: bool,
) -> dict[str, Any]:
    record = build_first_formula_probe(run_dir)
    prompt = _build_formula_probe_prompt(record)
    image_path = record.get("region_image_path") or record.get("page_image_path")
    if call_llm and image_path and settings.llm_configured:
        advisor = AzureLlmAdvisor(settings)
        advice = advisor.recommend_formula_from_image(
            prompt=prompt,
            image_bytes=Path(str(image_path)).read_bytes(),
            image_mime_type="image/png",
            max_output_tokens=max(settings.llm_max_output_tokens, 1024),
        )
        record["llm_probe"] = {
            "used": advice.used,
            "error": advice.error,
            "response": advice.raw,
            "prompt_preview": prompt[:1200],
        }
    else:
        record["llm_probe"] = {
            "used": False,
            "error": None if settings.llm_configured else "llm_not_configured",
            "response": None,
            "prompt_preview": prompt[:1200],
        }

    output_path = run_dir / "first_formula_probe.json"
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["artifact_path"] = str(output_path)
    return record


def build_first_formula_probe(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {run_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_path = Path(str(manifest.get("metadata", {}).get("source_path", "")))
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    markdown_path = _select_markdown_path(run_dir)
    markdown_text = markdown_path.read_text(encoding="utf-8")
    window = _find_first_placeholder_window(markdown_text)
    if window is None:
        return {
            "run_dir": str(run_dir),
            "source_path": str(source_path),
            "markdown_path": str(markdown_path),
            "placeholder_found": False,
        }

    line_map = _load_markdown_line_map(run_dir)
    anchored_page_number = _page_number_from_line_map(line_map, line_number=window.line_number)
    page_texts = _extract_pdf_page_texts(source_path) if source_path.suffix.lower() == ".pdf" else []
    best_page = _select_best_page_from_anchor(
        window=window,
        anchored_page_number=anchored_page_number,
        page_texts=page_texts,
    )
    image_path = None
    region_image_path = None
    region_match = None
    if best_page is not None and source_path.suffix.lower() == ".pdf":
        image_path = _render_pdf_page_image(
            source_path=source_path,
            page_number=best_page["page_number"],
            output_path=run_dir / "first_formula_probe_page.png",
        )
        region_match = _build_region_probe(
            source_path=source_path,
            page_number=best_page["page_number"],
            window=window,
            page_image_path=image_path,
            output_path=run_dir / "first_formula_probe_region.png",
        )
        if region_match is not None:
            region_image_path = Path(str(region_match["region_image_path"]))

    return {
        "run_dir": str(run_dir),
        "source_path": str(source_path),
        "markdown_path": str(markdown_path),
        "placeholder_found": True,
        "placeholder": {
            "line_number": window.line_number,
            "line_text": window.line_text,
            "context_before": list(window.context_before),
            "context_after": list(window.context_after),
            "context_text": window.context_text,
            "anchored_page_number": anchored_page_number,
        },
        "page_match": best_page,
        "page_image_path": str(image_path) if image_path else None,
        "region_match": region_match,
        "region_image_path": str(region_image_path) if region_image_path else None,
        "downstream_shape": {
            "preferred_contract": "patch_object_first",
            "notes": [
                "The LLM response should first be captured as a structured patch object.",
                "If the replacement is reviewable and anchorable, it can then be materialized back into markdown.",
                "A separate downstream object is only needed when the replacement cannot be safely inserted into markdown.",
            ],
        },
    }


def _select_markdown_path(run_dir: Path) -> Path:
    for candidate_name in ("final_resolved.md", "suggested_resolved.md", "result.md"):
        candidate = run_dir / candidate_name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No markdown artifact found in {run_dir}")


def _load_markdown_line_map(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "markdown_line_map.json"
    if not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _page_number_from_line_map(line_map: list[dict[str, Any]], *, line_number: int) -> int | None:
    for item in line_map:
        if int(item.get("line_number", 0)) != line_number:
            continue
        page_number = item.get("page_number")
        if isinstance(page_number, int) and page_number > 0:
            return page_number
    return None


def _find_first_placeholder_window(markdown_text: str) -> PlaceholderWindow | None:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines, start=1):
        if FORMULA_PLACEHOLDER not in line:
            continue
        before = _collect_context(lines, start_index=index - 2, direction=-1)
        after = _collect_context(lines, start_index=index, direction=1)
        return PlaceholderWindow(
            line_number=index,
            line_text=line,
            context_before=tuple(before),
            context_after=tuple(after),
        )
    return None


def _collect_context(lines: list[str], *, start_index: int, direction: int) -> list[str]:
    collected: list[str] = []
    cursor = start_index
    while 0 <= cursor < len(lines) and len(collected) < 4:
        value = lines[cursor].strip()
        cursor += direction
        if not value or FORMULA_PLACEHOLDER in value:
            continue
        collected.append(value)
    if direction < 0:
        collected.reverse()
    return collected


def _extract_pdf_page_texts(source_path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(source_path))
    return [
        {
            "page_number": page_number,
            "text": (page.extract_text() or "").strip(),
        }
        for page_number, page in enumerate(reader.pages, start=1)
    ]


def _select_best_page(window: PlaceholderWindow, *, page_texts: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_tokens = set(_TOKEN_PATTERN.findall(window.context_text))
    if not query_tokens:
        return None

    best_match: dict[str, Any] | None = None
    best_score = 0.0
    for page in page_texts:
        text = str(page.get("text", ""))
        page_tokens = set(_TOKEN_PATTERN.findall(text))
        if not page_tokens:
            continue
        overlap = query_tokens & page_tokens
        score = len(overlap) / max(len(query_tokens), 1)
        if score <= best_score:
            continue
        best_score = score
        best_match = {
            "page_number": int(page.get("page_number", 0)),
            "score": round(score, 4),
            "matched_tokens": sorted(overlap)[:24],
            "page_excerpt": _excerpt_for_page(text, overlap),
        }
    return best_match


def _select_best_page_from_anchor(
    *,
    window: PlaceholderWindow,
    anchored_page_number: int | None,
    page_texts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if anchored_page_number is not None:
        anchored_page = next(
            (page for page in page_texts if int(page.get("page_number", 0)) == anchored_page_number),
            None,
        )
        if anchored_page is not None:
            return {
                "page_number": anchored_page_number,
                "score": 1.0,
                "matched_tokens": [],
                "page_excerpt": _excerpt_for_page(str(anchored_page.get("text", "")), set()),
                "strategy": "line_anchor",
            }

    best_page = _select_best_page(window=window, page_texts=page_texts)
    if best_page is not None:
        best_page["strategy"] = "text_overlap_fallback"
    return best_page


def _excerpt_for_page(text: str, overlap: set[str], *, width: int = 280) -> str:
    if not text:
        return ""
    for token in sorted(overlap, key=len, reverse=True):
        index = text.find(token)
        if index >= 0:
            start = max(0, index - (width // 3))
            end = min(len(text), index + len(token) + (width // 2))
            snippet = text[start:end]
            return snippet if start == 0 else f"...{snippet}"
    return text[:width]


def _build_region_probe(
    *,
    source_path: Path,
    page_number: int,
    window: PlaceholderWindow,
    page_image_path: Path,
    output_path: Path,
) -> dict[str, Any] | None:
    import pdfplumber

    with pdfplumber.open(str(source_path)) as pdf:
        page = pdf.pages[page_number - 1]
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
        if not words:
            return None
        line_boxes = _group_words_into_lines(words)
        crop_box = _select_crop_box(
            line_boxes=line_boxes,
            context_before=window.context_before,
            context_after=window.context_after,
            page_width=float(page.width),
            page_height=float(page.height),
        )
        if crop_box is None:
            return None

        from PIL import Image

        page_image = Image.open(page_image_path)
        scale_x = page_image.width / float(page.width)
        scale_y = page_image.height / float(page.height)
        left, top, right, bottom = crop_box
        pixel_box = (
            max(0, int(left * scale_x)),
            max(0, int(top * scale_y)),
            min(page_image.width, int(right * scale_x)),
            min(page_image.height, int(bottom * scale_y)),
        )
        region_image = page_image.crop(pixel_box)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        region_image.save(output_path)

        return {
            "region_image_path": str(output_path),
            "pdf_bbox": {
                "left": round(left, 2),
                "top": round(top, 2),
                "right": round(right, 2),
                "bottom": round(bottom, 2),
            },
            "pixel_bbox": {
                "left": pixel_box[0],
                "top": pixel_box[1],
                "right": pixel_box[2],
                "bottom": pixel_box[3],
            },
        }


def _group_words_into_lines(words: list[dict[str, Any]]) -> list[LineBox]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    last_top: float | None = None
    for word in sorted(words, key=lambda item: (round(float(item["top"]), 1), float(item["x0"]))):
        word_top = float(word["top"])
        if last_top is None or abs(word_top - last_top) <= 2.5:
            current.append(word)
        else:
            groups.append(current)
            current = [word]
        last_top = word_top
    if current:
        groups.append(current)

    lines: list[LineBox] = []
    for group in groups:
        ordered = sorted(group, key=lambda item: float(item["x0"]))
        text = " ".join(str(item.get("text", "")) for item in ordered).strip()
        if not text:
            continue
        lines.append(
            LineBox(
                text=text,
                normalized_text=_normalize_text(text),
                x0=min(float(item["x0"]) for item in ordered),
                top=min(float(item["top"]) for item in ordered),
                x1=max(float(item["x1"]) for item in ordered),
                bottom=max(float(item["bottom"]) for item in ordered),
            )
        )
    return lines


def _select_crop_box(
    *,
    line_boxes: list[LineBox],
    context_before: tuple[str, ...],
    context_after: tuple[str, ...],
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float] | None:
    before_match = _find_anchor_line(line_boxes, list(reversed(context_before)))
    after_match = _find_anchor_line(
        line_boxes,
        list(context_after),
        min_top=(before_match.bottom + 2.0) if before_match is not None else None,
    )
    if before_match is None and after_match is None:
        return None

    if before_match is not None:
        start_top = max(before_match.top - 6.0, 0.0)
        left = max(before_match.x0 - 24.0, 0.0)
        right = min(max(before_match.x1 + 460.0, page_width * 0.92), page_width)
    else:
        start_top = 0.0
        left = 20.0
        right = max(page_width - 20.0, left + 40.0)

    end_top = after_match.top - 4.0 if after_match is not None else min(start_top + (page_height * 0.12), page_height)
    if end_top <= start_top:
        end_top = min(start_top + (page_height * 0.1), page_height)

    return (left, start_top, right, min(end_top, page_height))


def _find_anchor_line(
    line_boxes: list[LineBox],
    candidates: list[str],
    *,
    min_top: float | None = None,
) -> LineBox | None:
    for candidate in candidates:
        normalized_candidate = _normalize_text(candidate)
        if not normalized_candidate:
            continue
        best: LineBox | None = None
        best_score = 0
        for line in line_boxes:
            if min_top is not None and line.top < min_top:
                continue
            if normalized_candidate in line.normalized_text:
                score = len(normalized_candidate)
                if score > best_score:
                    best = line
                    best_score = score
        if best is not None:
            return best
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]+", "", text)


def _render_pdf_page_image(*, source_path: Path, page_number: int, output_path: Path) -> Path:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=False,
        do_picture_classification=False,
        do_picture_description=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_page_images=True,
        generate_picture_images=False,
        generate_table_images=False,
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    conversion = converter.convert(str(source_path))
    page = conversion.document.pages.get(page_number)
    if page is None or page.image is None or page.image.pil_image is None:
        raise ValueError(f"Unable to render page image for page {page_number}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page.image.pil_image.save(output_path)
    return output_path


def _build_formula_probe_prompt(record: dict[str, Any]) -> str:
    placeholder = record.get("placeholder", {})
    page_match = record.get("page_match", {})
    region_match = record.get("region_match", {})
    return (
        "You are reconstructing exactly one undecoded formula placeholder from a Korean insurance markdown export.\n"
        "Return JSON only with this shape:\n"
        '{"replacement_markdown":"...","normalized_math":"...","confidence":0.0,"reason":"...","render_as":"block|inline|table_cell","apply_as_patch":true}\n'
        "Rules:\n"
        "- Reconstruct only the first placeholder line.\n"
        "- Preserve nearby Korean labels and numbering.\n"
        "- The provided image is a focused crop around the placeholder region when available.\n"
        "- If the image does not provide enough evidence, set apply_as_patch to false and explain why.\n"
        f"Matched page number: {page_match.get('page_number')}\n"
        f"Page match score: {page_match.get('score')}\n"
        f"Region bbox: {json.dumps(region_match.get('pdf_bbox', {}), ensure_ascii=False)}\n"
        f"Context before: {json.dumps(placeholder.get('context_before', []), ensure_ascii=False)}\n"
        f"Placeholder line: {placeholder.get('line_text', '')}\n"
        f"Context after: {json.dumps(placeholder.get('context_after', []), ensure_ascii=False)}\n"
    )
