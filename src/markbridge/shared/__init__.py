"""Shared types used across MarkBridge modules."""

from .ir import (
    BlockKind,
    BlockIR,
    DocumentFormat,
    DocumentIR,
    SourceSpan,
    TableBlockIR,
    TableCellIR,
)

__all__ = [
    "BlockIR",
    "BlockKind",
    "DocumentFormat",
    "DocumentIR",
    "SourceSpan",
    "TableBlockIR",
    "TableCellIR",
]
