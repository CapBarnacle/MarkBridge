from markbridge.audit.document_ir import summarize_pipeline_result
from markbridge.pipeline.models import PipelineRequest, PipelineResult
from markbridge.shared.ir import BlockIR, BlockKind, DocumentFormat, DocumentIR, SourceSpan, TableBlockIR, TableCellIR
from markbridge.tracing.model import ParseTrace
from markbridge.validators.gate import HandoffDecision, QualityGateResult
from markbridge.validators.model import ValidationReport


def test_summarize_pipeline_result_reports_ir_coverage() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.XLSX,
        blocks=(
            BlockIR(
                kind=BlockKind.HEADING,
                text="Benefits",
                parser_block_ref="openpyxl:heading:0000",
                heading_level=2,
                source=SourceSpan(sheet="Benefits"),
                metadata={"heading_level": 2},
            ),
            TableBlockIR(
                parser_block_ref="openpyxl:table:0001",
                source=SourceSpan(sheet="Benefits", start_line=1, end_line=3),
                table_id="xlsx-table-1",
                title="Benefits",
                caption="Benefits",
                header_depth=1,
                cells=(
                    TableCellIR(row_index=0, column_index=0, text="항목", is_header=True),
                    TableCellIR(row_index=1, column_index=0, text="보험료"),
                ),
            ),
        ),
        metadata={
            "parser_id": "openpyxl",
            "source_name": "benefits.xlsx",
            "source_format": "xlsx",
        },
    )
    result = PipelineResult.create(
        request=PipelineRequest(source_path=__file__, document_format=DocumentFormat.XLSX),
        trace=ParseTrace.create(__file__, DocumentFormat.XLSX),
        route=None,
        validation=ValidationReport(issues=(), summary={}),
        handoff=QualityGateResult(
            decision=HandoffDecision.ACCEPT,
            summary="ok",
            reasons=(),
            metadata={},
        ),
        document=document,
        parser_id="openpyxl",
    )

    summary = summarize_pipeline_result(result, requested_input="benefits.xlsx", include_blocks=True)

    assert summary["status"] == "ok"
    assert summary["block_kind_counts"] == {"heading": 1, "table": 1}
    assert summary["coverage"]["parser_block_ref"]["ratio"] == 1.0
    assert summary["coverage"]["heading_level"]["ratio"] == 1.0
    assert summary["coverage"]["sheet_source"]["ratio"] == 1.0
    assert summary["coverage"]["table_header_depth"]["ratio"] == 1.0
    assert summary["coverage"]["table_title"]["ratio"] == 1.0
    assert len(summary["blocks"]) == 2
