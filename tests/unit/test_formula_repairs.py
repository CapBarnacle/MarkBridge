from markbridge.repairs.formula import generate_repair_candidates
from markbridge.tracing.model import DisplayExcerpt, IssueSeverity, TraceStage
from markbridge.validators.model import LocationRef, ValidationIssue, ValidationIssueCode


def test_generate_repair_candidates_for_formula_like_corruption() -> None:
    issue = ValidationIssue.create(
        code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        message="Suspicious broken glyphs detected in parsed text.",
        location=LocationRef(block_ref="block-13", line_hint="block 13"),
        excerpts=(
            DisplayExcerpt(
                label="broken-text",
                content="1.3. 해지율(      )에 관한 사항",
                highlight_text="",
                location_hint="block 13",
            ),
        ),
        details={"corruption_class": "inline_formula_corruption"},
        repairable=True,
    )

    candidates = generate_repair_candidates((issue,))

    assert len(candidates) == 1
    assert candidates[0].repair_type == "formula_reconstruction"
    assert candidates[0].origin == "deterministic"
    assert candidates[0].block_ref == "block-13"
    assert candidates[0].candidate_text is not None
    assert "해지율(q_{x+t}^{L})" in candidates[0].candidate_text
    assert candidates[0].normalized_math == "q_{x+t}^{L}"
    assert candidates[0].llm_recommended is False
    assert candidates[0].patch_proposal is not None
    assert candidates[0].patch_proposal.uncertain is False
    assert candidates[0].patch_proposal.replacement_text == "1.3. 해지율(q_{x+t}^{L})에 관한 사항"


def test_generate_repair_candidates_marks_placeholders_for_llm_review() -> None:
    issue = ValidationIssue.create(
        code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        message="Undecoded formula placeholders were emitted in markdown output.",
        location=LocationRef(block_ref="block-33", line_hint="block 33"),
        excerpts=(
            DisplayExcerpt(
                label="formula-placeholder",
                content="<!-- formula-not-decoded -->",
                highlight_text="<!-- formula-not-decoded -->",
                location_hint="block 33",
            ),
        ),
        details={"corruption_class": "formula_placeholder"},
        repairable=True,
    )

    candidates = generate_repair_candidates((issue,))

    assert len(candidates) == 1
    assert candidates[0].candidate_text is None
    assert candidates[0].llm_recommended is True
    assert candidates[0].strategy == "llm_required"
    assert candidates[0].patch_proposal is None


def test_generate_repair_candidates_does_not_use_hangul_parens_as_math_span() -> None:
    issue = ValidationIssue.create(
        code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        message="Suspicious broken glyphs detected in parsed text.",
        location=LocationRef(block_ref="block-21", line_hint="block 21"),
        excerpts=(
            DisplayExcerpt(
                label="broken-text",
                content="㈜  : 보험료 납입기간, t : 경과기간 (년수)",
                highlight_text="",
                location_hint="block 21",
            ),
        ),
        details={"corruption_class": "inline_formula_corruption"},
        repairable=True,
    )

    candidates = generate_repair_candidates((issue,))

    assert len(candidates) == 1
    assert candidates[0].candidate_text == "㈜ m : 보험료 납입기간, t : 경과기간 (년수)"
    assert candidates[0].normalized_math == "m"
    assert candidates[0].llm_recommended is True


def test_generate_repair_candidates_improves_table_formula_notation() -> None:
    issue = ValidationIssue.create(
        code=ValidationIssueCode.TEXT_CORRUPTION,
        severity=IssueSeverity.WARNING,
        stage=TraceStage.VALIDATION,
        message="Suspicious broken glyphs detected in parsed text.",
        location=LocationRef(block_ref="block-31", line_hint="table cell r2 c1"),
        excerpts=(
            DisplayExcerpt(
                label="broken-text",
                content="  ",
                highlight_text="",
                location_hint="table cell r2 c1",
            ),
        ),
        details={"corruption_class": "table_formula_corruption"},
        repairable=True,
    )

    candidates = generate_repair_candidates((issue,))

    assert len(candidates) == 1
    assert candidates[0].candidate_text == "q_{x+t}^{L}"
    assert candidates[0].normalized_math == "q_{x+t}^{L}"
    assert candidates[0].llm_recommended is False
