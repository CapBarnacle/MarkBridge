"""Deterministic inspection report models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from markbridge.shared.ir import DocumentFormat


@dataclass(frozen=True, slots=True)
class CommonInspectionFeatures:
    file_size_bytes: int | None = None
    page_count: int | None = None
    sheet_count: int | None = None
    detected_language: str | None = None
    complexity_score: float | None = None


@dataclass(frozen=True, slots=True)
class PdfInspectionFeatures:
    text_layer_coverage: float | None = None
    image_ratio: float | None = None
    table_candidate_count: int | None = None
    formula_candidate_count: int | None = None
    layout_variance: float | None = None
    ocr_necessity_estimate: float | None = None


@dataclass(frozen=True, slots=True)
class DocxInspectionFeatures:
    heading_style_availability: bool | None = None
    paragraph_count: int | None = None
    table_count: int | None = None
    nested_table_indicators: int | None = None
    floating_object_indicators: int | None = None


@dataclass(frozen=True, slots=True)
class XlsxInspectionFeatures:
    sheet_count: int | None = None
    used_range_density: float | None = None
    merged_cell_count: int | None = None
    formula_ratio: float | None = None
    multi_header_indicators: int | None = None
    repeated_region_indicators: int | None = None


@dataclass(frozen=True, slots=True)
class DocConversionFeatures:
    conversion_feasibility: bool | None = None
    conversion_output_quality_signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HwpInspectionFeatures:
    execution_feasibility: bool | None = None
    execution_route_candidates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InspectionReport:
    """Format-aware inspection output consumed by routing."""

    source_path: Path
    document_format: DocumentFormat
    common: CommonInspectionFeatures = field(default_factory=CommonInspectionFeatures)
    pdf: PdfInspectionFeatures | None = None
    docx: DocxInspectionFeatures | None = None
    xlsx: XlsxInspectionFeatures | None = None
    doc: DocConversionFeatures | None = None
    hwp: HwpInspectionFeatures | None = None
    warnings: tuple[str, ...] = ()
