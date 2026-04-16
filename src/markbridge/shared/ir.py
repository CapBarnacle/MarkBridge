"""Shared intermediate representation for normalized parser output."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    DOC = "doc"
    HWP = "hwp"


class BlockKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FORMULA = "formula"
    NOTE = "note"
    WARNING = "warning"
    IMAGE_REF = "image_ref"
    FOOTER = "footer"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Maps normalized content back to a source location."""

    page: int | None = None
    sheet: str | None = None
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class BlockIR:
    """Generic normalized block used by downstream stages."""

    kind: BlockKind
    text: str | None = None
    source: SourceSpan | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TableCellIR:
    """Minimal structural table cell model."""

    row_index: int
    column_index: int
    text: str
    row_span: int = 1
    column_span: int = 1
    is_header: bool = False


@dataclass(frozen=True, slots=True)
class TableBlockIR(BlockIR):
    """Table-specific IR with structural fields from the architecture spec."""

    kind: BlockKind = BlockKind.TABLE
    cells: tuple[TableCellIR, ...] = ()
    table_id: str | None = None
    title: str | None = None
    page_range: tuple[int, int] | None = None
    header_depth: int = 0
    merged_cells: bool = False
    nested_regions: tuple[str, ...] = ()
    continuation_of: str | None = None
    semantic_type: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class DocumentIR:
    """Normalized document container shared by all parser routes."""

    source_format: DocumentFormat
    blocks: tuple[BlockIR, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
