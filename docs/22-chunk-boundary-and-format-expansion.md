# 22. Chunk Boundary and Legacy Format Expansion

## Purpose

This document captures two near-term priorities:

1. make Markdown output more chunking-friendly across `pdf`, `docx`, and `xlsx`,
2. extend executable coverage for `doc` and eventually `hwp`.

The goal is not just prettier Markdown.
The goal is to emit stronger structural boundaries so downstream chunking can split on meaningful section starts while preserving auditability.

## Problem Statement

Current behavior is uneven across formats:

- `pdf` through `docling` often preserves heading-like Markdown such as `##` already.
- `docx` only promotes paragraphs to heading blocks when the Word style name contains `Heading`.
- `xlsx` is rendered mainly as tables and sheet content, with weak explicit section boundaries for chunking.
- `doc` has a conversion path in code but depends on LibreOffice runtime availability.
- `hwp` is accepted at intake but has no executable parser route.

This creates two practical risks:

- downstream chunking quality depends too heavily on source format and parser quirks,
- legacy office formats remain operationally incomplete.

## Current Format-Specific Behavior

### PDF

Current baseline:

- `docling` converts PDF to Markdown first
- parser stores that output in `DocumentIR.metadata["preferred_markdown"]`
- `_blocks_from_markdown()` rebuilds block structure from the Markdown
- headings already present in Markdown survive into final output

Implication:

- PDF currently has the best natural chunk-boundary behavior, assuming `docling` preserves headings well.
- This should be treated as the reference behavior for other formats.

### DOCX

Current baseline:

- `python-docx` reads paragraphs and tables directly
- a paragraph becomes `BlockKind.HEADING` only when its style name contains `Heading`
- all other text becomes plain paragraph blocks

Implication:

- documents with correct heading styles already produce `##` boundaries
- documents that visually look like headings but are stored as plain paragraphs lose chunk-friendly structure

Typical miss cases:

- numbered section titles like `1.`, `1.1`, `I.`, `가.`
- Korean business headers like `제1장`, `제1절`, `보장내용`, `보험금 지급`
- short standalone all-important titles that were not styled correctly in Word

### XLSX

Current baseline:

- `openpyxl` builds table blocks from sheet cells
- output is structurally useful as a table, but chunk boundaries are weak
- sheet names exist in metadata, but are not consistently surfaced as Markdown heading anchors

Implication:

- downstream chunkers do not get strong section boundaries per sheet or per logical table region
- retrieval can still work, but chunk segmentation is less controllable

### DOC

Current baseline:

- `.doc` can be converted to `.docx` through LibreOffice headless
- converted output is then parsed through the existing DOCX path
- route activation is already implemented but depends on `libreoffice` / `soffice` availability

Implication:

- `.doc` is not a design gap; it is a runtime dependency gap plus fidelity verification work

### HWP

Current baseline:

- intake accepts `.hwp`
- inspection emits an explicit warning
- runtime route set is empty

Implication:

- `.hwp` is still a true implementation gap, not just an environment gap

## Design Goal for Chunk Boundaries

Markdown output should expose chunking-friendly boundaries in two layers:

1. visible Markdown headings such as `##`
2. machine-readable boundary metadata that does not depend only on heading syntax

This dual approach is important because:

- some downstream chunkers split on Markdown headings directly
- others may need a safer structured signal before changing chunking behavior
- future heuristics may identify a likely boundary even when converting it into a visible heading would be too aggressive

## Proposed Boundary Signal Model

For each logical boundary candidate, MarkBridge should preserve:

- boundary type
- confidence
- reason
- source block or line reference
- whether the boundary was materialized into visible Markdown

Example conceptual fields:

- `boundary_kind = heading | sheet_start | table_title | section_marker`
- `boundary_reason = heading_style | heading_pattern | sheet_name | merged_header_band`
- `boundary_confidence = 0.0 - 1.0`
- `materialized_as_markdown_heading = true | false`

This can live in block metadata first, then later become a dedicated sidecar if needed.

## Proposed Rules by Format

### PDF

Policy:

- keep trusting `docling` heading preservation as the first choice
- do not aggressively rewrite parser-native headings unless there is strong evidence that structure was lost

Enhancements:

- record heading-derived boundary candidates in metadata even when the Markdown already contains `##`
- measure heading density and heading survival during routing-quality comparison

### DOCX

Policy:

- keep Word style-based heading detection
- add deterministic heading-pattern heuristics for paragraphs that look like section starts

Recommended heuristic signals:

- numbered prefixes:
  - `1.`
  - `1.1`
  - `I.`
  - `A.`
  - `가.`
- Korean section markers:
  - `제1장`
  - `제1절`
  - `제1조`
- short standalone lines with high title likelihood
- paragraphs followed by dense explanatory text or tables

Guardrails:

- avoid promoting long narrative sentences
- avoid promoting table cell text
- avoid overfitting to one insurer's formatting quirks without regression fixtures

### XLSX

Policy:

- emit strong chunk boundaries at least at sheet level
- optionally emit additional boundaries for obvious table-title or header-band regions

Recommended first-step rules:

- render each sheet start as a heading block using the sheet title
- if a table region is preceded by a merged-cell title row or obvious label row, consider materializing a subheading

Guardrails:

- do not invent semantic section labels when the workbook only contains raw tabular data
- prefer stable sheet-level boundaries over aggressive fine-grained splitting in v1

## Proposed Output Contract Changes

### Visible Markdown

Preferred near-term behavior:

- `pdf`: preserve parser-native headings
- `docx`: materialize confident heading candidates as `##`
- `xlsx`: materialize sheet starts as `##`

### Metadata

Add boundary hints to block metadata or a later sidecar so downstream systems can distinguish:

- explicit heading from source
- inferred heading from heuristic promotion
- non-heading chunk boundary candidate

Possible metadata fields:

- `chunk_boundary_candidate`
- `chunk_boundary_reason`
- `chunk_boundary_confidence`
- `chunk_boundary_materialized`

## Impact on Chunking

This work should improve:

- semantic chunk starts
- section-aligned retrieval
- chunk titles or prefixes in embeddings
- consistency across formats

This work should not yet assume:

- perfect section hierarchy reconstruction
- guaranteed heading depth recovery
- full table-to-section semantic understanding

## DOC Expansion Strategy

### Short Version

`doc` should be treated as a near-term executable expansion.

### Why it is feasible now

- route logic already exists
- conversion helper already exists
- downstream parsing can reuse the DOCX pipeline

### Remaining work

- ensure LibreOffice is available in the runtime environment
- validate conversion fidelity on sample insurance documents
- confirm heading and table preservation after conversion
- add regression tests for conversion success and failure paths

### Risk

- conversion may flatten layout or degrade tables on some samples
- therefore `.doc` support must be benchmarked, not assumed correct just because conversion runs

## HWP Expansion Strategy

### Short Version

`hwp` should be treated as a separate strategy decision before implementation.

### Feasible paths

1. conversion-first path
- convert `hwp` into `hwpx`, `docx`, or `pdf`
- then reuse existing parser stack

2. dedicated parser path
- add an HWP/HWPX parser library and map output into shared IR

3. external service or command adapter
- use a controlled converter outside the current Python-only parser set

### Recommended priority

Prefer conversion-first if it is operationally stable and on-prem deployable.

Reason:

- it reuses the existing IR, validation, repair, and handoff stack
- it reduces the amount of new parser-specific domain logic

### Main blocker

- we do not yet have an approved, reliable, on-prem executable path for `.hwp`

## Recommended Implementation Order

1. improve chunk-boundary signals for `docx`
2. add sheet-level heading boundaries for `xlsx`
3. add boundary metadata sidecar or block metadata fields
4. benchmark chunk-boundary quality on real samples
5. activate and verify `.doc` via LibreOffice
6. choose `hwp` strategy based on available conversion/parser options

## Success Criteria

### Chunk-boundary work succeeds when

- `pdf`, `docx`, and `xlsx` each emit stable, reviewable section boundaries
- downstream chunkers can split on `##` without severe over-segmentation
- boundary decisions remain traceable to source evidence or deterministic heuristics

### DOC expansion succeeds when

- `.doc` routes automatically when LibreOffice is available
- converted output produces reviewable Markdown with acceptable heading/table fidelity

### HWP expansion succeeds when

- there is at least one approved executable route
- output can enter the same IR, validation, repair, and handoff pipeline without special downstream exceptions

## Immediate Recommendation

The next concrete implementation should focus on chunk-boundary quality, not `hwp`.

Reason:

- chunk-boundary work improves all current supported formats
- `.doc` is mostly blocked on environment availability, not design
- `.hwp` still needs a route decision before coding begins
