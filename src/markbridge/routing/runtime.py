"""Runtime-aware deterministic routing for the current environment."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

from markbridge.inspection.model import InspectionReport
from markbridge.routing.model import LlmUsageMode, RouteLevel, RoutingDecision
from markbridge.shared.ir import DocumentFormat


@dataclass(frozen=True, slots=True)
class RuntimeParserStatus:
    parser_id: str
    installed: bool
    enabled: bool
    reason: str | None = None
    supported_formats: tuple[DocumentFormat, ...] = ()
    route_kind: str = "primary"


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def get_runtime_statuses() -> dict[str, RuntimeParserStatus]:
    docling_installed = _has_module("docling")
    pdfplumber_installed = _has_module("pdfplumber")
    pypdf_installed = _has_module("pypdf")
    docx_installed = _has_module("docx")
    openpyxl_installed = _has_module("openpyxl")
    markitdown_installed = _has_module("markitdown")
    libreoffice_installed = shutil.which("libreoffice") is not None or shutil.which("soffice") is not None
    antiword_installed = shutil.which("antiword") is not None
    hwp5txt_installed = shutil.which("hwp5txt") is not None
    return {
        "docling": RuntimeParserStatus(
            "docling",
            docling_installed,
            docling_installed,
            None if docling_installed else "not installed",
            supported_formats=(DocumentFormat.PDF,),
            route_kind="primary",
        ),
        "pdfplumber": RuntimeParserStatus(
            "pdfplumber",
            pdfplumber_installed,
            False,
            "secondary candidate not enabled by policy" if pdfplumber_installed else "not installed",
            supported_formats=(DocumentFormat.PDF,),
            route_kind="secondary",
        ),
        "pypdf": RuntimeParserStatus(
            "pypdf",
            pypdf_installed,
            pypdf_installed,
            None if pypdf_installed else "not installed",
            supported_formats=(DocumentFormat.PDF,),
            route_kind="fallback",
        ),
        "python-docx": RuntimeParserStatus(
            "python-docx",
            docx_installed,
            docx_installed,
            None if docx_installed else "not installed",
            supported_formats=(DocumentFormat.DOCX,),
            route_kind="primary",
        ),
        "openpyxl": RuntimeParserStatus(
            "openpyxl",
            openpyxl_installed,
            openpyxl_installed,
            None if openpyxl_installed else "not installed",
            supported_formats=(DocumentFormat.XLSX,),
            route_kind="primary",
        ),
        "markitdown": RuntimeParserStatus(
            "markitdown",
            markitdown_installed,
            False,
            "experimental candidate" if markitdown_installed else "not installed",
            route_kind="experimental",
        ),
        "libreoffice": RuntimeParserStatus(
            "libreoffice",
            libreoffice_installed,
            libreoffice_installed,
            "conversion route not available" if not libreoffice_installed else None,
            supported_formats=(DocumentFormat.DOC,),
            route_kind="primary",
        ),
        "antiword": RuntimeParserStatus(
            "antiword",
            antiword_installed,
            antiword_installed,
            "text fallback route not available" if not antiword_installed else None,
            supported_formats=(DocumentFormat.DOC,),
            route_kind="degraded_fallback",
        ),
        "hwp5txt": RuntimeParserStatus(
            "hwp5txt",
            hwp5txt_installed,
            hwp5txt_installed,
            "HWP text route not available" if not hwp5txt_installed else None,
            supported_formats=(DocumentFormat.HWP,),
            route_kind="text_route",
        ),
    }


def executable_candidates_for_format(document_format: DocumentFormat) -> tuple[str, ...]:
    statuses = get_runtime_statuses()
    candidates_by_format = {
        DocumentFormat.PDF: ("docling", "pypdf"),
        DocumentFormat.DOCX: ("python-docx",),
        DocumentFormat.XLSX: ("openpyxl",),
        DocumentFormat.DOC: ("libreoffice", "antiword"),
        DocumentFormat.HWP: ("hwp5txt",),
    }
    return tuple(
        parser_id
        for parser_id in candidates_by_format.get(document_format, ())
        if statuses.get(parser_id) and statuses[parser_id].enabled
    )


def choose_route(
    report: InspectionReport,
    *,
    parser_override: str | None = None,
    llm_used: bool = False,
) -> RoutingDecision:
    statuses = get_runtime_statuses()
    parser_id = "unsupported"
    rationale: list[str] = []
    if parser_override:
        candidates = executable_candidates_for_format(report.document_format)
        status = statuses.get(parser_override)
        if status and status.enabled and parser_override in candidates:
            return RoutingDecision(
                level=RouteLevel.DETERMINISTIC_WITH_LLM_ROUTING if llm_used else RouteLevel.DETERMINISTIC_ONLY,
                primary_parser=parser_override,
                llm_usage=LlmUsageMode.ROUTING if llm_used else LlmUsageMode.NONE,
                rationale=(
                    "parser override applied before deterministic default selection.",
                    f"override={parser_override}",
                ),
                policy_metadata={
                    "document_format": report.document_format.value,
                    "runtime_enabled": {k: v.enabled for k, v in statuses.items()},
                    "override_applied": True,
                },
            )
        rationale.append(f"parser override ignored: {parser_override}")

    if report.document_format is DocumentFormat.PDF:
        if statuses["docling"].enabled:
            parser_id = "docling"
            rationale.append("docling is enabled and preferred for PDF fidelity.")
        elif statuses["pypdf"].enabled:
            parser_id = "pypdf"
            rationale.append("pypdf is the only enabled PDF fallback in the current environment.")
    elif report.document_format is DocumentFormat.DOCX and statuses["python-docx"].enabled:
        parser_id = "python-docx"
        rationale.append("python-docx is enabled for DOCX routing.")
    elif report.document_format is DocumentFormat.XLSX and statuses["openpyxl"].enabled:
        parser_id = "openpyxl"
        rationale.append("openpyxl is enabled for XLSX routing.")
    elif report.document_format is DocumentFormat.DOC and statuses["libreoffice"].enabled:
        parser_id = "libreoffice"
        rationale.append("LibreOffice conversion route is enabled.")
    elif report.document_format is DocumentFormat.DOC and statuses["antiword"].enabled:
        parser_id = "antiword"
        rationale.append("antiword text fallback route is enabled.")
    elif report.document_format is DocumentFormat.HWP and statuses["hwp5txt"].enabled:
        parser_id = "hwp5txt"
        rationale.append("hwp5txt text route is enabled.")

    level = RouteLevel.DETERMINISTIC_ONLY
    llm_usage = LlmUsageMode.ROUTING if llm_used else LlmUsageMode.NONE
    if parser_id == "unsupported":
        rationale.append("No enabled parser is available for this document format.")

    return RoutingDecision(
        level=level,
        primary_parser=parser_id,
        llm_usage=llm_usage,
        rationale=tuple(rationale),
        policy_metadata={
            "document_format": report.document_format.value,
            "runtime_enabled": {k: v.enabled for k, v in statuses.items()},
            "override_applied": False,
        },
    )
