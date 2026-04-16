from markbridge.shared.ir import BlockIR, BlockKind, DocumentFormat, DocumentIR, TableBlockIR, TableCellIR
from markbridge.tracing import IssueSeverity, TraceStage
from markbridge.validators.execution import validate_document
from markbridge.validators.gate import HandoffDecision, evaluate_handoff
from markbridge.validators.model import ValidationIssue, ValidationIssueCode


def test_validate_document_flags_private_use_glyphs() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(kind=BlockKind.PARAGRAPH, text="1.1. 이율(  )에 관한 사항"),
            BlockIR(kind=BlockKind.PARAGRAPH, text="보험료 산식  "),
        ),
    )

    report = validate_document(document, markdown_text="1.1. 이율(  )에 관한 사항\n보험료 산식  ")

    glyph_issues = [issue for issue in report.issues if issue.message.startswith("Suspicious broken glyphs")]
    issue = glyph_issues[0]
    assert issue.code is ValidationIssueCode.TEXT_CORRUPTION
    assert len(glyph_issues) == 2
    assert issue.details["private_use_count"] == 1
    assert issue.details["corruption_class"] == "inline_formula_corruption"
    assert issue.excerpts[0].location_hint == "block 0"
    assert issue.excerpts[0].content == "1.1. 이율(  )에 관한 사항"


def test_validate_document_flags_formula_placeholders_from_markdown() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(BlockIR(kind=BlockKind.FORMULA, text=None),),
    )

    report = validate_document(document, markdown_text="<!-- formula-not-decoded -->\n\n본문")

    issue = _find_issue(report.issues, "Undecoded formula placeholders")
    assert issue.code is ValidationIssueCode.TEXT_CORRUPTION
    assert issue.details["formula_placeholder_count"] == 1
    assert issue.details["corruption_class"] == "formula_placeholder"
    assert issue.excerpts[0].location_hint == "markdown output"


def test_validate_document_flags_private_use_glyphs_in_table_cells() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
          TableBlockIR(
              cells=(
                  TableCellIR(row_index=0, column_index=0, text="t"),
                  TableCellIR(row_index=1, column_index=0, text="  "),
              ),
              table_id="table-1",
          ),
        ),
    )

    report = validate_document(document, markdown_text="| t |\n| --- |\n|    |")

    issue = _find_issue(report.issues, "Suspicious broken glyphs")
    assert issue.code is ValidationIssueCode.TEXT_CORRUPTION
    assert issue.details["corruption_class"] == "table_formula_corruption"
    assert issue.excerpts[0].location_hint == "table cell r2 c1"
    assert issue.excerpts[0].highlight_text == ""


def test_validation_issue_snapshot_includes_details_metadata() -> None:
    issue = ValidationIssue.create(
        code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        message="Snapshot metadata check",
        details={"detectors": ["private_use_glyphs"]},
        repairable=True,
    )

    snapshot = issue.to_snapshot()

    assert snapshot.metadata["details"] == {"detectors": ["private_use_glyphs"]}


def test_evaluate_handoff_deduplicates_reason_codes() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(kind=BlockKind.PARAGRAPH, text="수식 "),
            BlockIR(kind=BlockKind.PARAGRAPH, text="또 다른 수식 "),
        ),
    )

    report = validate_document(
        document,
        markdown_text="수식 \n\n<!-- formula-not-decoded -->",
    )
    handoff = evaluate_handoff(report)

    assert handoff.decision is HandoffDecision.DEGRADED_ACCEPT
    assert handoff.reasons == ("text_corruption",)


def _find_issue(issues: tuple[ValidationIssue, ...], prefix: str) -> ValidationIssue:
    for issue in issues:
        if issue.message.startswith(prefix):
            return issue
    raise AssertionError(f"Issue starting with {prefix!r} was not found.")
