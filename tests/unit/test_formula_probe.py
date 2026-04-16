from pathlib import Path

from markbridge.experiments.formula_probe import _group_words_into_lines, _select_crop_box, build_first_formula_probe


def test_build_first_formula_probe_finds_first_placeholder_and_context(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source_path = tmp_path / "sample.txt"
    source_path.write_text("placeholder source", encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        '{"metadata":{"source_path":"' + str(source_path) + '"}}',
        encoding="utf-8",
    )
    (run_dir / "final_resolved.md").write_text(
        "\n".join(
            [
                "## 2.1. 시산보험료 산출에 관한 사항",
                "가. 기준연납순보험료",
                "",
                "<!-- formula-not-decoded -->",
                "",
                "나. 순보험료",
            ]
        ),
        encoding="utf-8",
    )

    record = build_first_formula_probe(run_dir)

    assert record["placeholder_found"] is True
    assert record["placeholder"]["line_number"] == 4
    assert record["placeholder"]["context_before"] == [
        "## 2.1. 시산보험료 산출에 관한 사항",
        "가. 기준연납순보험료",
    ]
    assert record["placeholder"]["context_after"] == ["나. 순보험료"]
    assert record["downstream_shape"]["preferred_contract"] == "patch_object_first"


def test_build_first_formula_probe_prefers_saved_line_anchor_page_number(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source_path = tmp_path / "sample.pdf"
    source_path.write_bytes(b"%PDF-1.4\n% anchor test\n")
    (run_dir / "manifest.json").write_text(
        '{"metadata":{"source_path":"' + str(source_path) + '"}}',
        encoding="utf-8",
    )
    (run_dir / "final_resolved.md").write_text(
        "\n".join(
            [
                "앞 문맥",
                "<!-- formula-not-decoded -->",
                "뒤 문맥",
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "markdown_line_map.json").write_text(
        '[{"line_number":2,"text":"<!-- formula-not-decoded -->","refs":["block-7"],"page_number":4}]',
        encoding="utf-8",
    )

    from markbridge.experiments import formula_probe as module

    original_extract = module._extract_pdf_page_texts
    original_render = module._render_pdf_page_image
    original_region = module._build_region_probe
    try:
        module._extract_pdf_page_texts = lambda _: [  # type: ignore[assignment]
            {"page_number": 4, "text": "앞 문맥 수식 뒤 문맥"},
            {"page_number": 5, "text": "다른 페이지"},
        ]
        module._render_pdf_page_image = lambda **kwargs: run_dir / "first_formula_probe_page.png"  # type: ignore[assignment]
        module._build_region_probe = lambda **kwargs: None  # type: ignore[assignment]
        record = build_first_formula_probe(run_dir)
    finally:
        module._extract_pdf_page_texts = original_extract  # type: ignore[assignment]
        module._render_pdf_page_image = original_render  # type: ignore[assignment]
        module._build_region_probe = original_region  # type: ignore[assignment]

    assert record["placeholder"]["anchored_page_number"] == 4
    assert record["page_match"]["page_number"] == 4
    assert record["page_match"]["strategy"] == "line_anchor"


def test_select_crop_box_uses_context_anchors() -> None:
    lines = _group_words_into_lines(
        [
            {"text": "가.", "x0": 40.0, "top": 200.0, "x1": 50.0, "bottom": 208.0},
            {"text": "기준연납순보험료", "x0": 55.0, "top": 200.0, "x1": 130.0, "bottom": 208.0},
            {"text": "수식토큰", "x0": 60.0, "top": 218.0, "x1": 120.0, "bottom": 226.0},
            {"text": "나.", "x0": 40.0, "top": 250.0, "x1": 50.0, "bottom": 258.0},
            {"text": "순보험료", "x0": 55.0, "top": 250.0, "x1": 100.0, "bottom": 258.0},
        ]
    )

    crop_box = _select_crop_box(
        line_boxes=lines,
        context_before=("가. 기준연납순보험료",),
        context_after=("나. 순보험료",),
        page_width=600.0,
        page_height=800.0,
    )

    assert crop_box is not None
    left, top, right, bottom = crop_box
    assert left == 16.0
    assert right == 590.0
    assert top <= 194.0
    assert bottom >= 240.0
