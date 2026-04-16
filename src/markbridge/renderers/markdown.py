"""Markdown rendering for the shared IR."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re

from markbridge.shared.ir import BlockIR, BlockKind, DocumentIR, TableBlockIR


def render_markdown(document: DocumentIR) -> str:
    return render_markdown_with_map(document).markdown


@dataclass(frozen=True, slots=True)
class MarkdownLineMapEntry:
    line_number: int
    text: str
    refs: tuple[str, ...]
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class MarkdownRenderResult:
    markdown: str
    line_map: tuple[MarkdownLineMapEntry, ...]


def render_markdown_with_map(document: DocumentIR) -> MarkdownRenderResult:
    preferred_markdown = document.metadata.get("preferred_markdown")
    if isinstance(preferred_markdown, str) and preferred_markdown.strip():
        markdown = preferred_markdown.strip()
        line_map = _build_line_map_from_block_metadata(markdown, document.blocks)
        if line_map is None:
            line_map = _build_line_map_from_blocks(markdown, document.blocks)
        return MarkdownRenderResult(markdown=markdown, line_map=line_map)

    parts: list[str] = []
    line_map: list[MarkdownLineMapEntry] = []
    current_line = 1
    for index, block in enumerate(document.blocks):
        block_ref = f"block-{index}"
        rendered, block_lines = _render_block_with_map(block, block_ref=block_ref)
        if not rendered:
            continue
        if parts:
            line_map.append(MarkdownLineMapEntry(line_number=current_line, text="", refs=()))
            current_line += 1
        parts.append(rendered)
        for offset, item in enumerate(block_lines):
            line_map.append(
                MarkdownLineMapEntry(
                    line_number=current_line + offset,
                    text=item["text"],
                    refs=tuple(item["refs"]),
                    page_number=_block_page_number(block),
                )
            )
        current_line += len(block_lines)
    return MarkdownRenderResult(markdown="\n\n".join(parts).strip(), line_map=tuple(line_map))


def _render_block(block: BlockIR) -> str:
    return _render_block_with_map(block, block_ref="block")[0]


def _render_block_with_map(block: BlockIR, *, block_ref: str) -> tuple[str, list[dict[str, object]]]:
    if isinstance(block, TableBlockIR):
        return _render_table(block, block_ref=block_ref)
    if block.kind is BlockKind.HEADING:
        level = _heading_level(block)
        text = f"{'#' * level} {block.text}"
        return text, [{"text": text, "refs": [block_ref]}]
    if block.kind is BlockKind.NOTE:
        return _render_note(block, block_ref=block_ref)
    text = block.text or ""
    if not text:
        return "", []
    lines = text.splitlines() or [text]
    return text, [{"text": line, "refs": [block_ref]} for line in lines]


def _render_note(block: BlockIR, *, block_ref: str) -> tuple[str, list[dict[str, object]]]:
    text = block.text or ""
    if not text:
        return "", []
    rendered_lines: list[str] = []
    line_map: list[dict[str, object]] = []
    for line in text.splitlines():
        rendered = f"> {line}" if line else ">"
        rendered_lines.append(rendered)
        line_map.append({"text": rendered, "refs": [block_ref]})
    return "\n".join(rendered_lines), line_map


def _render_table(block: TableBlockIR, *, block_ref: str) -> tuple[str, list[dict[str, object]]]:
    if not block.cells:
        return "", []
    max_row = max(cell.row_index for cell in block.cells)
    max_col = max(cell.column_index for cell in block.cells)
    grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    row_refs: dict[int, list[str]] = {}
    for cell in block.cells:
        grid[cell.row_index][cell.column_index] = cell.text
        row_refs.setdefault(cell.row_index, []).append(f"table cell r{cell.row_index + 1} c{cell.column_index + 1}")

    if len(grid) < 2:
        grid.append(["" for _ in range(max_col + 1)])
    header = grid[0]
    separator = ["---" for _ in header]
    rows = [header, separator, *grid[1:]]
    table_lines = [f"| {' | '.join(row)} |" for row in rows]
    line_map = [
        {"text": table_lines[0], "refs": [block_ref, *row_refs.get(0, [])]},
        {"text": table_lines[1], "refs": [block_ref]},
    ]
    for row_index, line in enumerate(table_lines[2:], start=1):
        line_map.append({"text": line, "refs": [block_ref, *row_refs.get(row_index, [])]})
    table_text = "\n".join(table_lines)
    if block.merged_cells:
        preface = f"[Complex table preserved: {block.table_id or 'table'}]"
        return f"{preface}\n\n{table_text}", [{"text": preface, "refs": [block_ref]}, {"text": "", "refs": []}, *line_map]
    return table_text, line_map


def _build_line_map_from_blocks(markdown: str, blocks: tuple[BlockIR, ...]) -> tuple[MarkdownLineMapEntry, ...]:
    markdown_lines = markdown.splitlines()
    refs_by_line: list[list[str]] = [[] for _ in markdown_lines]
    page_by_line: list[int | None] = [None for _ in markdown_lines]
    line_index = 0

    for block_index, block in enumerate(blocks):
        expected_lines = _render_block_with_map(block, block_ref=f"block-{block_index}")[1]
        block_page_number = _block_page_number(block)
        for expected in expected_lines:
            match_index = _find_matching_line(markdown_lines, expected, start_index=line_index)
            if match_index is None:
                continue
            for ref in (str(ref) for ref in expected["refs"]):
                if ref not in refs_by_line[match_index]:
                    refs_by_line[match_index].append(ref)
            if page_by_line[match_index] is None:
                page_by_line[match_index] = block_page_number
            line_index = max(line_index, match_index + 1)

    return tuple(
        MarkdownLineMapEntry(
            line_number=index + 1,
            text=line,
            refs=tuple(refs_by_line[index]),
            page_number=page_by_line[index],
        )
        for index, line in enumerate(markdown_lines)
    )


def _build_line_map_from_block_metadata(markdown: str, blocks: tuple[BlockIR, ...]) -> tuple[MarkdownLineMapEntry, ...] | None:
    markdown_lines = markdown.splitlines()
    refs_by_line: list[list[str]] = [[] for _ in markdown_lines]
    page_by_line: list[int | None] = [None for _ in markdown_lines]
    any_mapping = False

    for block_index, block in enumerate(blocks):
        line_numbers = block.metadata.get("markdown_line_numbers")
        if not isinstance(line_numbers, list) or not all(isinstance(item, int) for item in line_numbers):
            continue
        expected_lines = _render_block_with_map(block, block_ref=f"block-{block_index}")[1]
        if not expected_lines:
            continue
        any_mapping = True
        block_page_number = _block_page_number(block)
        for expected_index, expected in enumerate(expected_lines):
            if expected_index >= len(line_numbers):
                break
            line_number = line_numbers[expected_index]
            if line_number < 1 or line_number > len(markdown_lines):
                continue
            target_refs = refs_by_line[line_number - 1]
            for ref in (str(ref) for ref in expected["refs"]):
                if ref not in target_refs:
                    target_refs.append(ref)
            if page_by_line[line_number - 1] is None:
                page_by_line[line_number - 1] = block_page_number

    if not any_mapping:
        return None

    return tuple(
        MarkdownLineMapEntry(
            line_number=index + 1,
            text=line,
            refs=tuple(refs_by_line[index]),
            page_number=page_by_line[index],
        )
        for index, line in enumerate(markdown_lines)
    )


def _block_page_number(block: BlockIR) -> int | None:
    if block.source is not None and block.source.page is not None:
        return int(block.source.page)
    metadata_page = block.metadata.get("page")
    if isinstance(metadata_page, int):
        return metadata_page
    metadata_page_number = block.metadata.get("page_number")
    if isinstance(metadata_page_number, int):
        return metadata_page_number
    page_range = block.metadata.get("page_range")
    if (
        isinstance(page_range, tuple)
        and len(page_range) == 2
        and isinstance(page_range[0], int)
        and isinstance(page_range[1], int)
        and page_range[0] == page_range[1]
    ):
        return page_range[0]
    return None


def _find_matching_line(markdown_lines: list[str], expected: dict[str, object], *, start_index: int) -> int | None:
    expected_text = str(expected["text"])
    expected_refs = tuple(str(ref) for ref in expected["refs"])
    normalized_expected = _normalize_line_for_matching(expected_text)

    if not normalized_expected:
        for index in range(start_index, len(markdown_lines)):
            if not markdown_lines[index].strip():
                return index
        return None

    best_index: int | None = None
    best_score = -1

    for index in range(start_index, len(markdown_lines)):
        candidate = markdown_lines[index]
        normalized_candidate = _normalize_line_for_matching(candidate)
        if not normalized_candidate:
            continue
        score = _match_score(normalized_candidate, normalized_expected, expected_refs)
        if score > best_score:
            best_index = index
            best_score = score
            if score >= 120:
                break

    return best_index if best_score > 0 else None


def _match_score(candidate: str, expected: str, expected_refs: tuple[str, ...]) -> int:
    if candidate == expected:
        return 200
    if candidate.endswith(expected) or expected.endswith(candidate):
        return 120
    if expected in candidate or candidate in expected:
        return 90

    if any(ref.startswith("table cell") for ref in expected_refs):
        expected_tokens = [token for token in expected.split() if token]
        matched_tokens = sum(token in candidate for token in expected_tokens)
        if matched_tokens >= max(1, min(2, len(expected_tokens))):
            return 70 + matched_tokens

    if _contains_all_significant_tokens(candidate, expected):
        return 60

    return -1


def _contains_all_significant_tokens(candidate: str, expected: str) -> bool:
    tokens = [token for token in expected.split() if len(token) > 1 or ord(token[0]) >= 0xE000]
    if not tokens:
        return False
    return all(token in candidate for token in tokens[:4])


def _normalize_line_for_matching(text: str) -> str:
    value = html.unescape(text).strip()
    if not value:
        return ""
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"^\s*[-*+]\s+", "", value)
    value = re.sub(r"^\s*\d+[.)]\s*", "", value)
    if value.startswith("|") and value.endswith("|"):
        value = value.strip("|")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _heading_level(block: BlockIR) -> int:
    metadata_level = block.metadata.get("level")
    if isinstance(metadata_level, int):
        return max(1, min(6, metadata_level))
    return 2
