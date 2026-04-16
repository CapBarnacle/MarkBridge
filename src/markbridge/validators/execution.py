"""Concrete deterministic validation helpers."""

from __future__ import annotations

from collections.abc import Iterable

from markbridge.shared.ir import BlockIR, DocumentIR, TableBlockIR
from markbridge.tracing import DisplayExcerpt, IssueSeverity, TraceStage
from markbridge.validators.model import LocationRef, ValidationIssue, ValidationIssueCode, ValidationReport

FORMULA_PLACEHOLDER = "<!-- formula-not-decoded -->"


def validate_document(document: DocumentIR, *, markdown_text: str) -> ValidationReport:
    issues: list[ValidationIssue] = []
    issues.extend(_check_empty_output(document, markdown_text))
    issues.extend(_check_text_corruption(document, markdown_text=markdown_text))
    issues.extend(_check_table_structure(document))
    summary = {
        "issue_count": len(issues),
        "error_count": sum(issue.severity is IssueSeverity.ERROR for issue in issues),
        "warning_count": sum(issue.severity is IssueSeverity.WARNING for issue in issues),
    }
    return ValidationReport(issues=tuple(issues), summary=summary)


def _check_empty_output(document: DocumentIR, markdown_text: str) -> list[ValidationIssue]:
    if document.blocks or markdown_text.strip():
        return []
    return [
        ValidationIssue.create(
            code=ValidationIssueCode.EMPTY_OUTPUT,
            severity=IssueSeverity.ERROR,
            stage=TraceStage.VALIDATION,
            message="The parser produced empty document output.",
            repairable=False,
        )
    ]


def _check_text_corruption(document: DocumentIR, *, markdown_text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    glyph_detected = False
    formula_detected = False

    for index, block in enumerate(document.blocks):
        block_ref = f"block-{index}"
        block_texts = _iter_block_text_candidates(block, index=index)
        for candidate in block_texts:
            candidate_text = candidate["text"]
            if not candidate_text:
                continue

            replacement_hits = candidate_text.count("\ufffd") + candidate_text.count("�")
            private_use_hits = list(_find_private_use_characters(candidate_text))
            formula_hits = candidate_text.count(FORMULA_PLACEHOLDER)

            if replacement_hits or private_use_hits:
                glyph_detected = True
                highlight = "�" if replacement_hits else private_use_hits[0]
                corruption_class = _classify_corruption(
                    candidate_text,
                    location_hint=candidate["location_hint"],
                    has_placeholder=False,
                )
                issues.append(
                    ValidationIssue.create(
                        code=ValidationIssueCode.TEXT_CORRUPTION,
                        severity=IssueSeverity.WARNING,
                        stage=TraceStage.VALIDATION,
                        message="Suspicious broken glyphs detected in parsed text.",
                        location=LocationRef(block_ref=block_ref, line_hint=candidate["location_hint"]),
                        excerpts=(
                            DisplayExcerpt(
                                label="broken-text",
                                content=_excerpt_around(candidate_text, highlight),
                                highlight_text=highlight,
                                location_hint=candidate["location_hint"],
                                metadata={
                                    "replacement_count": replacement_hits,
                                    "private_use_count": len(private_use_hits),
                                },
                            ),
                        ),
                        details={
                            "detectors": _detectors_for_glyph_issue(replacement_hits, len(private_use_hits)),
                            "replacement_count": replacement_hits,
                            "private_use_count": len(private_use_hits),
                            "corruption_class": corruption_class,
                            "formula_like": corruption_class != "symbol_only_corruption",
                        },
                        repairable=True,
                    )
                )

            if formula_hits:
                formula_detected = True
                corruption_class = _classify_corruption(
                    candidate_text,
                    location_hint=candidate["location_hint"],
                    has_placeholder=True,
                )
                issues.append(
                    ValidationIssue.create(
                        code=ValidationIssueCode.TEXT_CORRUPTION,
                        severity=IssueSeverity.WARNING,
                        stage=TraceStage.VALIDATION,
                        message="Undecoded formula placeholders were emitted in markdown output.",
                        location=LocationRef(block_ref=block_ref, line_hint=candidate["location_hint"]),
                        excerpts=(
                            DisplayExcerpt(
                                label="formula-placeholder",
                                content=_excerpt_around(candidate_text, FORMULA_PLACEHOLDER),
                                highlight_text=FORMULA_PLACEHOLDER,
                                location_hint=candidate["location_hint"],
                            ),
                        ),
                        details={
                            "detectors": ["formula_placeholders"],
                            "formula_placeholder_count": formula_hits,
                            "corruption_class": corruption_class,
                            "formula_like": True,
                        },
                        repairable=True,
                    )
                )

    if not glyph_detected:
        markdown_private_use = list(_find_private_use_characters(markdown_text))
        markdown_replacement_count = markdown_text.count("\ufffd") + markdown_text.count("�")
        if markdown_private_use or markdown_replacement_count:
            highlight = "�" if markdown_replacement_count else markdown_private_use[0]
            issues.append(
                ValidationIssue.create(
                    code=ValidationIssueCode.TEXT_CORRUPTION,
                    severity=IssueSeverity.WARNING,
                    stage=TraceStage.VALIDATION,
                    message="Suspicious broken glyphs detected in parsed text.",
                    location=LocationRef(line_hint="markdown output"),
                    excerpts=(
                        DisplayExcerpt(
                            label="broken-text",
                            content=_excerpt_around(markdown_text, highlight),
                            highlight_text=highlight,
                            location_hint="markdown output",
                            metadata={
                                "replacement_count": markdown_replacement_count,
                                "private_use_count": len(markdown_private_use),
                            },
                        ),
                    ),
                    details={
                        "detectors": _detectors_for_glyph_issue(markdown_replacement_count, len(markdown_private_use)),
                        "replacement_count": markdown_replacement_count,
                        "private_use_count": len(markdown_private_use),
                        "corruption_class": "structure_loss",
                        "formula_like": True,
                    },
                    repairable=True,
                )
            )

    if not formula_detected:
        markdown_formula_count = markdown_text.count(FORMULA_PLACEHOLDER)
        if markdown_formula_count:
            issues.append(
                ValidationIssue.create(
                    code=ValidationIssueCode.TEXT_CORRUPTION,
                    severity=IssueSeverity.WARNING,
                    stage=TraceStage.VALIDATION,
                    message="Undecoded formula placeholders were emitted in markdown output.",
                    location=LocationRef(line_hint="markdown output"),
                    excerpts=(
                        DisplayExcerpt(
                            label="formula-placeholder",
                            content=_excerpt_around(markdown_text, FORMULA_PLACEHOLDER),
                            highlight_text=FORMULA_PLACEHOLDER,
                            location_hint="markdown output",
                        ),
                    ),
                    details={
                        "detectors": ["formula_placeholders"],
                        "formula_placeholder_count": markdown_formula_count,
                        "corruption_class": "formula_placeholder",
                        "formula_like": True,
                    },
                    repairable=True,
                )
            )

    return issues


def _check_table_structure(document: DocumentIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, block in enumerate(document.blocks):
        if not isinstance(block, TableBlockIR):
            continue
        header_cells = [cell for cell in block.cells if cell.row_index == 0 and cell.text.strip()]
        if not header_cells:
            issues.append(
                ValidationIssue.create(
                    code=ValidationIssueCode.TABLE_STRUCTURE,
                    severity=IssueSeverity.WARNING,
                    stage=TraceStage.VALIDATION,
                    message="Table appears to have no non-empty header row.",
                    location=LocationRef(block_ref=f"table-{index}", table_id=block.table_id),
                    repairable=True,
                )
            )
        row_shapes: dict[int, int] = {}
        for cell in block.cells:
            row_shapes[cell.row_index] = row_shapes.get(cell.row_index, 0) + 1
        if row_shapes:
            counts = set(row_shapes.values())
            if len(counts) > 2:
                severity = IssueSeverity.WARNING if block.merged_cells or block.metadata.get("source") == "markdown_table" else IssueSeverity.ERROR
                issues.append(
                    ValidationIssue.create(
                        code=ValidationIssueCode.TABLE_STRUCTURE,
                        severity=severity,
                        stage=TraceStage.VALIDATION,
                        message="Table row widths vary unexpectedly and may indicate structural corruption.",
                        location=LocationRef(block_ref=f"table-{index}", table_id=block.table_id),
                        repairable=True,
                    )
                )
    return issues


def _find_private_use_characters(text: str) -> Iterable[str]:
    for character in text:
        codepoint = ord(character)
        if 0xE000 <= codepoint <= 0xF8FF:
            yield character


def _excerpt_around(text: str, marker: str, *, width: int = 240) -> str:
    if not text:
        return ""
    marker_index = text.find(marker)
    if marker_index == -1:
        return text[:width]
    start = max(0, marker_index - (width // 3))
    end = min(len(text), marker_index + len(marker) + (width // 2))
    excerpt = text[start:end]
    return excerpt if start == 0 else f"...{excerpt}"


def _detectors_for_glyph_issue(replacement_count: int, private_use_count: int) -> list[str]:
    detectors: list[str] = []
    if replacement_count:
        detectors.append("replacement_characters")
    if private_use_count:
        detectors.append("private_use_glyphs")
    return detectors


def _classify_corruption(text: str, *, location_hint: str, has_placeholder: bool) -> str:
    if has_placeholder:
        return "formula_placeholder"
    lowered_hint = location_hint.lower()
    if lowered_hint.startswith("table cell"):
        return "table_formula_corruption"
    if _looks_formula_like(text):
        return "inline_formula_corruption"
    return "symbol_only_corruption"


def _looks_formula_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(keyword in stripped for keyword in ("이율(", "위험률(", "해지율(", "보험료", "해약환급금")):
        return True
    if any(marker in stripped for marker in ("(", ")", "[", "]", "+", "=", "≤", "≥", "%")):
        return True
    private_use_count = sum(1 for _ in _find_private_use_characters(stripped))
    if private_use_count >= 2:
        return True
    return False


def _iter_block_text_candidates(block: BlockIR, *, index: int) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if block.text:
        candidates.append({"text": block.text, "location_hint": f"block {index}"})

    if isinstance(block, TableBlockIR):
        for cell in block.cells:
            if not cell.text:
                continue
            candidates.append(
                {
                    "text": cell.text,
                    "location_hint": f"table cell r{cell.row_index + 1} c{cell.column_index + 1}",
                }
            )

    return candidates
