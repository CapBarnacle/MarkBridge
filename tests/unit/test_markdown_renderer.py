from markbridge.renderers.markdown import render_markdown_with_map
from markbridge.shared.ir import BlockIR, BlockKind, DocumentFormat, DocumentIR, TableBlockIR, TableCellIR


def test_render_markdown_with_map_tracks_block_and_table_cell_refs() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(kind=BlockKind.HEADING, text="제목"),
            TableBlockIR(
                table_id="table-1",
                cells=(
                    TableCellIR(row_index=0, column_index=0, text="항목"),
                    TableCellIR(row_index=1, column_index=0, text="  "),
                ),
            ),
        ),
    )

    rendered = render_markdown_with_map(document)

    assert rendered.markdown
    assert rendered.line_map[0].refs == ("block-0",)
    assert any("block-1" in line.refs for line in rendered.line_map)
    assert any("table cell r2 c1" in line.refs for line in rendered.line_map)


def test_render_markdown_with_map_keeps_refs_for_preferred_markdown() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(kind=BlockKind.HEADING, text="1.1. 이율(  )에 관한 사항"),
            TableBlockIR(
                table_id="table-1",
                cells=(
                    TableCellIR(row_index=0, column_index=0, text="t"),
                    TableCellIR(row_index=1, column_index=0, text="  "),
                ),
            ),
        ),
        metadata={
            "preferred_markdown": "## 1.1. 이율(  )에 관한 사항\n\n| t |\n| --- |\n|    |"
        },
    )

    rendered = render_markdown_with_map(document)

    assert any(line.text == "## 1.1. 이율(  )에 관한 사항" and "block-0" in line.refs for line in rendered.line_map)
    assert any(line.text == "|    |" and "table cell r2 c1" in line.refs for line in rendered.line_map)


def test_render_markdown_with_map_does_not_lose_later_refs_after_one_mismatch() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(kind=BlockKind.HEADING, text="1.2. 위험률에 관한 사항"),
            BlockIR(kind=BlockKind.PARAGRAPH, text="무배당 예정 질병장해 50%이상 발생률(     )"),
            BlockIR(kind=BlockKind.HEADING, text="1.3. 해지율(      )에 관한 사항"),
            TableBlockIR(
                table_id="table-1",
                cells=(
                    TableCellIR(row_index=0, column_index=0, text="t"),
                    TableCellIR(row_index=1, column_index=0, text="  "),
                    TableCellIR(row_index=1, column_index=1, text="10.0%"),
                ),
            ),
            BlockIR(kind=BlockKind.PARAGRAPH, text="<!-- formula-not-decoded -->"),
        ),
        metadata={
            "preferred_markdown": "\n".join(
                [
                    "## 1.2. 위험률에 관한 사항",
                    "",
                    "- 무배당 예정 질병장해 50%이상 발생률(     )",
                    "",
                    "## 1.3. 해지율(      )에 관한 사항",
                    "",
                    "| t | 0 |",
                    "| --- | --- |",
                    "|    | 10.0% |",
                    "",
                    "<!-- formula-not-decoded -->",
                ]
            )
        },
    )

    rendered = render_markdown_with_map(document)

    assert any(line.line_number == 1 and "block-0" in line.refs for line in rendered.line_map)
    assert any(line.line_number == 3 and "block-1" in line.refs for line in rendered.line_map)
    assert any(line.line_number == 5 and "block-2" in line.refs for line in rendered.line_map)
    assert any(line.line_number == 9 and "block-3" in line.refs for line in rendered.line_map)
    assert any(line.line_number == 9 and "table cell r2 c1" in line.refs for line in rendered.line_map)
    assert any(line.line_number == 11 and "block-4" in line.refs for line in rendered.line_map)


def test_render_markdown_with_map_prefers_explicit_markdown_line_numbers() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(
                kind=BlockKind.HEADING,
                text="1.2. 위험률에 관한 사항",
                metadata={"markdown_line_numbers": [1]},
            ),
            BlockIR(
                kind=BlockKind.LIST,
                text="무배당 예정 질병장해 50%이상 발생률(     )",
                metadata={"markdown_line_numbers": [3]},
            ),
            TableBlockIR(
                table_id="table-1",
                cells=(
                    TableCellIR(row_index=0, column_index=0, text="t"),
                    TableCellIR(row_index=1, column_index=0, text="  "),
                    TableCellIR(row_index=1, column_index=1, text="10.0%"),
                ),
                metadata={"markdown_line_numbers": [5, 6, 7]},
            ),
        ),
        metadata={
            "preferred_markdown": "\n".join(
                [
                    "## 1.2. 위험률에 관한 사항",
                    "",
                    "- 무배당 예정 질병장해 50%이상 발생률(     )",
                    "",
                    "| t | 0 |",
                    "| --- | --- |",
                    "|    | 10.0% |",
                ]
            )
        },
    )

    rendered = render_markdown_with_map(document)

    assert rendered.line_map[0].refs == ("block-0",)
    assert rendered.line_map[2].refs == ("block-1",)
    assert "block-2" in rendered.line_map[4].refs
    assert "table cell r2 c1" in rendered.line_map[6].refs


def test_render_markdown_with_map_carries_page_number_from_block_metadata() -> None:
    document = DocumentIR(
        source_format=DocumentFormat.PDF,
        blocks=(
            BlockIR(
                kind=BlockKind.HEADING,
                text="1.2. 위험률에 관한 사항",
                metadata={"markdown_line_numbers": [1], "page_number": 3},
            ),
            BlockIR(
                kind=BlockKind.PARAGRAPH,
                text="본문",
                metadata={"markdown_line_numbers": [3], "page_number": 3},
            ),
        ),
        metadata={
            "preferred_markdown": "\n".join(
                [
                    "## 1.2. 위험률에 관한 사항",
                    "",
                    "본문",
                ]
            )
        },
    )

    rendered = render_markdown_with_map(document)

    assert rendered.line_map[0].page_number == 3
    assert rendered.line_map[2].page_number == 3
