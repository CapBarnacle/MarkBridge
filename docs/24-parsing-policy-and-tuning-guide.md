# 24. Parsing Policy and Tuning Guide

## Purpose

This document is the working source of truth for MarkBridge parsing policy.

It serves four purposes at once:

1. explain the parsing layer conceptually,
2. explain the current implementation technically,
3. record parser-policy decisions and tuning rationale,
4. provide a stable place to keep updating parsing behavior as tuning continues.

When parser behavior changes, this document should be updated together with code and tests.

## Product Boundary

MarkBridge is the parsing layer of a life-insurance CRM AI Assistant pipeline.

It is responsible for:

- ingesting business documents,
- selecting an executable parser route,
- normalizing outputs into shared structure,
- rendering Markdown,
- detecting parse-quality issues,
- generating deterministic and optional LLM repair candidates,
- assembling resolved Markdown when appropriate,
- handing downstream the best available Markdown with traceable evidence.

It is not currently responsible for:

- chunking itself,
- embedding generation,
- retrieval orchestration,
- answer generation.

## Core Parsing Philosophy

### 1. Source fidelity first

Markdown should stay as faithful as practical to source structure and source meaning.

This does not mean literal visual reproduction.
It means preserving the structure that downstream chunking, retrieval, and review will depend on:

- headings,
- tables,
- lists,
- section boundaries,
- formula-bearing spans,
- source-relative order.

### 2. Deterministic structure before LLM help

Parsing, structure detection, routing, and first-pass issue detection should be deterministic wherever possible.

LLM is allowed only after deterministic detection, mainly for:

- parser comparison or routing assistance,
- bounded repair of detected corruption,
- review-oriented reconstruction.

LLM is not the primary parser.

### 3. Common IR before Markdown

Every parser route should produce a shared IR before later stages act on the document.

This keeps validation, rendering, trace, and repair logic stable across formats.

### 4. Traceability is part of parsing quality

If the system cannot explain:

- which parser ran,
- where structure came from,
- where corruption was detected,
- why a repair was chosen,

then the parse quality is operationally incomplete even if the Markdown looks acceptable.

### 5. Chunking-friendly output matters

MarkBridge does not chunk documents itself, but it must emit Markdown and metadata that make downstream chunking sane.

This means parsing policy should explicitly care about:

- section boundaries,
- heading survival,
- over-large table cells,
- layout artifacts that destroy chunk quality.

## End-to-End Parsing Flow

1. ingest input document
2. run deterministic inspection
3. choose an executable route
4. parse into shared IR
5. render Markdown and line map
6. validate output quality
7. generate deterministic repair candidates
8. optionally generate LLM repair candidates
9. assemble resolved Markdown
10. decide downstream handoff
11. export trace and artifacts

Primary code paths:

- API entry: `src/markbridge/api/app.py`
- service orchestration: `src/markbridge/api/service.py`
- pipeline orchestration: `src/markbridge/pipeline/orchestrator.py`
- parser implementation: `src/markbridge/parsers/basic.py`
- renderer: `src/markbridge/renderers/markdown.py`
- validation: `src/markbridge/validators/execution.py`

## Deterministic Inspection Policy

Inspection is not full parsing.
It is a low-cost feature-extraction stage used to support routing and diagnostics.

Current examples by format:

- PDF:
  - page count
  - text-layer coverage
  - table-candidate count
- DOCX:
  - heading-style availability
  - paragraph count
  - table count
- XLSX:
  - sheet count
  - merged-cell count
  - formula ratio
- DOC:
  - conversion feasibility
- HWP:
  - explicit unsupported warning

Inspection policy rules:

- inspection should stay deterministic
- inspection may estimate quality risk
- inspection must not trigger OCR
- inspection must not fabricate parser availability

## Routing Policy

Routing must be limited to parser routes that are:

- supported by project policy,
- installed in the current runtime,
- enabled in the active route set.

Current active route policy:

- PDF: `docling` baseline, `pypdf` fallback/comparison
- DOCX: `python-docx`
- XLSX: `openpyxl`
- DOC: `libreoffice` conversion route when runtime is available
- HWP: no active route yet

Routing principles:

- deterministic baseline first
- optional LLM recommendation second
- recommendation does not automatically override baseline
- recommendation must beat baseline on observed quality signals

Current quality signals used in parser comparison include:

- heading count
- long-line collapse risk
- average line length
- corruption density

## IR Policy

IR means Intermediate Representation.

It is the common structural form used after parser execution and before rendering, validation, and repair.

Current core types:

- `DocumentIR`
- `BlockIR`
- `TableBlockIR`
- `TableCellIR`
- `SourceSpan`

Current block kinds:

- heading
- paragraph
- list
- table
- formula
- note
- warning
- image_ref
- footer

IR policy rules:

- preserve source-relative ordering
- preserve enough structure for validation and chunking support
- preserve table cell positions for true tables
- preserve line/page hints where possible
- do not overcommit to semantics that the parser did not actually recover

## Markdown Rendering Policy

There are two major rendering modes.

### 1. Preferred Markdown mode

Used when a parser already produced a strong Markdown form.

Current examples:

- `docling`
- `markitdown`

Policy:

- keep parser-native Markdown when it is likely more source-faithful
- rebuild block refs and line mapping around it
- avoid unnecessary rewriting

### 2. IR-rendered Markdown mode

Used when the parser produced structure but not authoritative Markdown.

Current examples:

- `python-docx`
- `openpyxl`
- `pypdf`

Policy:

- render headings as `##`
- render tables as Markdown tables when they are truly structural tables
- keep line mapping stable enough for UI review and repair anchoring

## DOCX Parsing Policy

DOCX is currently the format with the most practical tuning complexity.

### Goals

- preserve heading structure even when Word styles are inconsistent
- preserve paragraph/table order
- avoid collapsing layout-heavy documents into giant undifferentiated text
- emit chunk-friendly Markdown

### Current DOCX heading policy

Promote a paragraph to `HEADING` when one of these holds:

1. Word style name contains `Heading`
2. Word uses a custom title-like style name such as `첫제목`, `두번째제목`, or another style name containing `제목`
3. numbered heading pattern matches
4. Korean section-marker pattern matches
5. short title heuristic matches conservatively

Examples of currently recognized heading-like patterns:

- `1.`
- `1.1`
- `1)`
- `제1장`
- `제1절`
- short standalone business titles such as `보장내용`
- circled-number section titles such as `① 보험계약조회 및 보험료납입` when section context is strong

Examples of patterns that are now intentionally *not* promoted to `##` by default:

- `(1)`
- `(2)`
- body-like circled-number lines such as `① 계약정보 : ...`

Reason:

- parenthesized enumerations like `(1)` are often too granular for top-level Markdown chunk boundaries
- body-like circled-number lines often appear inside tables or explanatory paragraphs

Exception:

- circled-number labels such as `①`, `②`, `③` may be promoted when they look like short section titles and either:
  - are followed by a table, or
  - participate in a nearby circled-number section sequence
- this is a contextual recovery rule, not a blanket circled-number promotion policy

Examples of heading-like style cases now explicitly handled:

- standard Word heading styles
- custom Korean title styles such as `첫제목`
- custom Korean title styles such as `두번째제목`

Guardrails:

- long narrative sentences should not be promoted
- promotion should remain conservative
- tests must lock both positive and negative examples

This policy exists because insurance business documents often fail in two different ways:

1. they use no heading style at all, even though the text is clearly a section title
2. they use custom Word styles instead of standard `Heading 1/2/...`

Both cases now require explicit parser support.

### Current DOCX heading-depth policy

Heading detection and heading depth are separate decisions.

Current policy:

- top-level recovered section headings typically render as `##`
- deeper recovered section headings may render as `###` or below when the source provides enough evidence

Current evidence sources for depth:

- standard Word heading styles such as `Heading 1`, `Heading 2`, `Heading 3`
- custom Korean title styles such as `첫제목`, `두번째제목`, `세번째제목`
- numbered structures such as `1.` vs `1.1`
- Korean section markers such as `장`, `절`, `조`

Examples:

- `보험종목의 명칭` with `첫제목` style -> `##`
- `1형 : 무배당 종신보험 표준형` with `두번째제목` style -> `###`
- `1.1 가입대상` -> `###`

Reason:

- rendering every heading as `##` preserves some chunk boundaries
- but loses useful source hierarchy that can help review and future chunking policy

### Current DOCX ordering policy

Paragraphs and tables must be parsed in original document order.

This matters because a large amount of business meaning depends on:

- heading -> table
- heading -> body
- heading -> table -> note

Past bug:

- parsing all paragraphs first and all tables later broke document order
- this caused tables to appear under the wrong section in Markdown

Current rule:

- iterate paragraph/table blocks in original body order

### Current DOCX table policy

Not every Word table should remain a Markdown table.

We distinguish between:

1. true structural tables
2. layout tables used only to position long text blocks

#### True structural tables

Examples:

- multi-column comparison tables
- `구분 | 내용` style information tables
- tabular business fields with clear row/column meaning

Policy:

- preserve as `TableBlockIR`
- render as Markdown table
- when upper-category cells appear blank because of vertical merge or rowspan-like DOCX structure, apply conservative carry-forward normalization before rendering

#### Layout tables

Examples:

- one-column tables used to hold long enumerated guidance
- layout shells where the “table” is really a text container

Policy:

- preserve the container as a note-like boxed block when it is effectively a one-column caution or guidance shell
- flatten the inner content into chunkable text blocks instead of preserving a giant Markdown table shell
- preserve heading-like enum lines as chunk-boundary candidates
- preserve bullets and notices as list-like blocks where possible

Reason:

- layout tables often destroy chunking quality
- one-cell Markdown tables with huge bodies are poor chunk anchors
- some tables are real tables, but others are only layout containers around enumerated guidance text

### Current DOCX layout-table flattening policy

When a DOCX table is effectively a one-column layout shell:

- do not keep it as a Markdown table by default
- preserve that region as a note-like block so downstream still knows it was boxed/grouped content
- split text into headings, lists, and paragraphs inside the note-like block
- keep enum-style lines such as `(1)`, `(2)`, `(3)` as structured text by default instead of automatically promoting them to `##`

This is a chunking-quality policy, not a visual fidelity policy.

Typical case:

- a one-cell or one-column DOCX table contains a long operational guidance block
- the source author used a table only to control layout spacing
- preserving that as one giant Markdown table cell hurts chunking more than it helps fidelity

Counter-case:

- a true multi-column business table such as `구분 | 내용`
- this should stay a Markdown table and must not be flattened

### Current DOCX merged-cell and carry-forward policy

Many insurance DOCX tables express hierarchy through vertically merged first-column or second-column cells.

Typical symptom in naive Markdown output:

- the first row contains a category such as `내방`
- later related rows appear as:
  - `|  | 대리인 | ... |`
  - instead of
  - `| 내방 | 대리인 | ... |`

Current policy:

- for true multi-column DOCX tables, apply conservative carry-forward normalization in early columns
- only carry forward short category-like values
- only carry forward when later columns in the row still contain real content
- do not blindly fill every blank cell

Reason:

- many blank cells in DOCX are not semantically empty
- they are visual continuations of a vertically merged parent category
- downstream chunking and review both become clearer when the parent category is made explicit again

Guardrails:

- carry-forward is limited and conservative
- long free-text cells should not be propagated
- rows that are actually independent should not inherit unrelated parents
- after carry-forward and duplicate suppression, do not automatically collapse away now-empty columns unless repeated evidence shows that the pattern is safe across recent same-format regressions

### Current DOCX order-preservation policy

DOCX content must keep the original interleaving of:

- paragraph
- table
- paragraph
- table

The parser must not:

- collect all paragraphs first,
- then append all tables later.

That older behavior created real section drift bugs.

Concrete failure example:

- a heading such as `3) 대리인` appeared correctly,
- but the table that visually belonged under it was emitted later under another section such as `3) 우편접수`

This is now treated as a parser correctness bug, not a cosmetic issue.

## Mandatory Regression Validation Workflow

Every parsing-rule change must be validated in three layers:

1. unit tests for the intended positive and negative cases
2. live reparse of the target document that motivated the rule change
3. regression comparison against recent outputs from the same file type

This is mandatory for parser-policy changes, not optional cleanup.

### Why this workflow exists

Parsing heuristics are highly format-local and often insurer-template-specific.

A rule that improves one DOCX sample can easily damage:

- another DOCX with different layout-table usage,
- another PDF whose parser-native heading structure is already correct,
- downstream chunk boundaries that looked stable before the change.

Because of that, parser tuning must not be accepted based only on one motivating document.

### Required regression scope

For any parser-policy change:

- identify the target format first, such as DOCX or PDF
- select the motivating document that should improve
- select at least one recent control document of the same format that should remain stable
- when the change is high-risk, select at least two recent control documents of the same format

Examples:

- DOCX heading heuristic change:
  - positive case: the DOCX that failed to surface the intended section boundary
  - control case: a recent DOCX whose heading/table behavior was already acceptable
- DOCX table normalization change:
  - positive case: the DOCX with duplicated merged-cell labels
  - control case: a recent DOCX with true multi-column tables that must not collapse

### Preferred evidence sources

Use recent run artifacts under the durable work root first:

- `.markbridge/runs/<run_id>/result.md`
- `.markbridge/runs/<run_id>/final_resolved.md`
- `.markbridge/runs/<run_id>/<source-full-name>-1.md`
- `.markbridge/runs/<run_id>/manifest.json`

Use `manifest.json` to recover:

- `source_name`
- `source_path`
- `source_uri`

If older evidence still lives under `/tmp/markbridge`, it may be used as historical reference, but new regression validation should be recorded from `.markbridge/runs`.

### Required execution steps

1. Add or update unit tests that lock both the intended improvement and at least one negative case.
2. Reparse the motivating source document with the current backend code.
3. Compare the new output against the most recent previous output for the same document when available.
4. Reparse at least one recent same-format control document.
5. Check that the control document does not show unwanted structural drift.

### What must be compared

The comparison should focus on structural output, not only raw line-by-line diff volume.

Required checks:

- expected heading materialization appears or remains stable
- boxed-note or layout-container handling improves only where intended
- table headers and cell repetition do not regress
- chunk-boundary-relevant `##` structure does not drift unexpectedly
- canonical markdown selection is still consistent when downstream policy is affected

### Minimum record that must be left behind

After validation, record the evidence in session docs.

At minimum capture:

- the motivating document
- the same-format control document or documents
- the run directories or artifact paths used for before/after comparison
- the specific structural differences that changed
- whether any control document stayed unchanged or had acceptable deltas

The minimum places to update are:

- `docs/08-session-history.md`
- `docs/17-resume-brief.md` when the change materially affects restart context

### Current standing examples

Recent DOCX tuning already established a practical pattern for this workflow:

- `300233_계약관계자변경.docx` is a useful DOCX control document for box-preservation and merged-cell normalization checks
- `300138_라이프앱가능업무.docx` is a useful DOCX positive case for contextual circled-number heading promotion

Future DOCX heading or layout heuristics should be checked against both before merging.

## XLSX Parsing Policy

### Goals

- preserve sheet-level structure
- preserve table cells for truly tabular content
- emit at least one reliable chunk boundary per sheet

Current rules:

- each worksheet title becomes a heading block
- sheet content is rendered as table structure when applicable

Reason:

- sheet names are often the only reliable section boundary in spreadsheets

## PDF Parsing Policy

### Goals

- prefer source-faithful Markdown when possible
- avoid OCR
- preserve parser-native heading structure

Current rules:

- `docling` is preferred when available
- OCR stays disabled
- parser-native Markdown is kept as `preferred_markdown`
- headings already emitted by `docling` should survive

PDF policy note:

- PDF chunk-boundary quality is currently strongest when `docling` preserves headings well
- this behavior is treated as a practical reference point for DOCX/XLSX tuning

## DOC Parsing Policy

Current policy:

- convert `.doc` to `.docx`
- then reuse the DOCX path

This is already architecturally supported.
The current blocker is runtime availability of LibreOffice.

Policy implications:

- `.doc` is primarily an environment and fidelity problem, not a domain-model problem
- conversion must still be benchmarked because successful conversion does not guarantee acceptable structure

## HWP Parsing Policy

Current policy:

- accept intake
- return explicit unsupported `hold` at execution time

Future policy must choose one of:

1. conversion-first
2. dedicated parser
3. external adapter/service

Until then:

- do not pretend HWP is executable
- keep the unsupported state explicit and trace-visible

## Validation Policy

Validation is the canonical detector of parse-quality issues.

Current major checks:

- empty output
- text corruption
- table structure anomalies

Current important corruption classes:

- `inline_formula_corruption`
- `table_formula_corruption`
- `formula_placeholder`
- `symbol_only_corruption`
- `structure_loss`

Validation policy rules:

- deterministic detection first
- issue records are the source of truth
- trace may summarize issues, but validators own canonical issue state

## Repair Policy

Repair is not unrestricted rewriting.

Current stages:

1. deterministic repair candidate generation
2. optional LLM repair candidate generation
3. winner selection by issue
4. patch application into resolved Markdown

Repair policy rules:

- deterministic repair first
- LLM only after deterministic issue detection
- patch proposals must stay reviewable
- unresolved placeholder residue can block resolved Markdown from becoming canonical downstream input

## Chunk-Boundary Policy

This is the most important parsing-policy topic for downstream quality right now.

### Current stance

MarkBridge does not chunk documents itself, but parsing policy must expose chunk-friendly boundaries.

### Why visible headings alone are not enough

If the parser only writes `##`, downstream chunking has very limited information:

- some boundaries should always split
- some should split only when the current section is too large
- some are table-internal boundaries and should stay attached to surrounding context

### Boundary metadata policy

MarkBridge should preserve machine-readable boundary signals alongside Markdown.

Current examples already in block metadata:

- `chunk_boundary_candidate`
- `chunk_boundary_reason`
- `chunk_boundary_confidence`
- `chunk_boundary_materialized`

Typical reasons:

- `heading_style`
- `heading_pattern.numbered`
- `heading_pattern.korean_section`
- `heading_pattern.short_title`
- `heading_pattern.parenthesized`
- `sheet_name`
- `markdown_heading`

### Why parser policy and chunker policy must be aligned

Parser policy detects candidate boundaries.
Chunker policy decides which candidate boundaries should become real chunk splits.

These are not the same decision.

Examples:

- a top-level `Heading` style should almost always split
- a parenthesized item inside a flattened layout table may split only when the current chunk grows too large
- a sheet title should split strongly
- a short inferred title may split more conservatively

This is why adding metadata is more durable than only adding more `##`.

## Current Known Weaknesses

### 1. Chunk boundaries are improved but not complete

- some lower-level boundaries like `(가)`, `①`, `②` still need document-driven tuning
- section depth is still heuristic rather than canonical

### 2. Table preservation vs flattening remains a judgment problem

- some “tables” are layout shells and should be flattened
- some should remain true tables
- this distinction will continue to need sample-driven tuning

### 3. Parser-native and IR-native paths still behave differently

- `docling` PDF and `python-docx` DOCX do not originate from the same structure quality
- policy must remain format-aware

### 4. `.doc` and `.hwp` are still incomplete operationally

- `.doc` needs runtime activation
- `.hwp` still needs a route decision

## Recent Tuning History

This section should be updated whenever parser tuning changes behavior materially.

### T-001. DOCX heading promotion beyond Word style

Added conservative heading heuristics for plain paragraphs so business documents without proper Word heading styles still emit section boundaries.

Representative cases:

- `1. 보장내용`
- `제1장 보장내용`
- short standalone title lines like `보장내용`

Negative guardrail case:

- long ordinary explanatory sentences must remain paragraphs
- `1)`, `2)`, `(1)`, `(2)` level enumerations should not automatically become top-level `##` boundaries

Selective exception case:

- some business-section labels written as `3) 대리인`, `4) 중요 확인 사항` should still become headings when they clearly behave like section titles

### T-002. XLSX sheet-name heading emission

Added sheet-level heading blocks so spreadsheets produce stable chunk starts.

### T-003. Markdown-origin heading boundary metadata

Added boundary metadata even for parser-native Markdown headings so PDF and Markdown-origin paths can feed future chunker policy more consistently.

### T-004. DOCX layout-table flattening

Added a policy to flatten one-column layout tables into chunkable text blocks rather than preserving giant one-cell Markdown tables.

Representative cases:

- one-column operational guidance blocks
- long `(1)`, `(2)`, `(3)` enumerated instructions inside a single layout cell

Non-target case:

- true multi-column information tables must remain tables

### T-005. DOCX paragraph-table order preservation

Fixed DOCX parsing so paragraphs and tables keep original source order.
This prevents tables from drifting into the wrong section in Markdown.

Representative failure that motivated the fix:

- `3) 대리인` heading rendered in place
- but the related table appeared much later near `3) 우편접수`

### T-006. DOCX custom title-style recognition

Added support for title-like custom Word styles, especially Korean style names containing `제목`.

Representative cases:

- `첫제목`
- `두번째제목`

Reason:

- some converted insurance documents use custom title styles rather than standard `Heading` styles
- these documents are not “unstyled plain paragraphs”; they are “styled with nonstandard title names”

### T-007. DOCX merged-cell carry-forward normalization

Added conservative carry-forward handling for multi-column DOCX tables where vertically merged category cells otherwise appear blank in later rows.

Representative case:

- `내방 | 모두 방문 | ...`
- followed by a row that naively becomes `|  | 대리인 | ... |`
- now normalized toward `| 내방 | 대리인 | ... |`

Reason:

- this restores parent-category meaning without flattening the whole table

### T-008. DOCX heading-depth recovery

Added heading-depth recovery so DOCX headings are no longer rendered as uniformly flat `##`.

Representative cases:

- `첫제목` -> `##`
- `두번째제목` -> `###`
- `1.` -> `##`
- `1.1` -> `###`

Reason:

- source hierarchy is part of structural fidelity
- depth-aware Markdown is closer to the original document than a flat heading surface

## Recommended Update Discipline

When parsing behavior changes, update this document in the same PR or change set.

At minimum, add or revise:

- the affected format policy section
- any changed rule in chunk-boundary policy
- a new entry under `Recent Tuning History`
- relevant tests

## Current Resume Targets

If parser tuning resumes later, reopen these first:

- `src/markbridge/parsers/basic.py`
- `src/markbridge/renderers/markdown.py`
- `tests/unit/test_pipeline.py`
- `docs/22-chunk-boundary-and-format-expansion.md`
- `docs/23-chunk-boundary-and-legacy-format-plan.md`
- this document

## One-Sentence Summary

MarkBridge parsing policy is to produce the most source-grounded, reviewable, chunking-friendly Markdown possible through deterministic structure recovery first, bounded repair second, and format-aware tuning that preserves traceability throughout.
