"""Base parser contract for all format-specific parser implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markbridge.inspection.model import InspectionReport
from markbridge.shared.ir import DocumentFormat, DocumentIR


@dataclass(frozen=True, slots=True)
class ParseRequest:
    source_path: Path
    document_format: DocumentFormat
    inspection: InspectionReport | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseResult:
    parser_id: str
    document: DocumentIR
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract parser boundary between routing and normalization."""

    parser_id: str
    supported_formats: tuple[DocumentFormat, ...]

    @abstractmethod
    def parse(self, request: ParseRequest) -> ParseResult:
        """Parse a source document into shared IR."""

