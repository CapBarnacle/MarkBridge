# 23. Chunk Boundary and Legacy Format Execution Plan

Status note:

- This document is an earlier execution plan.
- Use [31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md) as the current task list and planning anchor.
- Keep this document only for background context and older workstream detail.

## Purpose

This plan turns the current priority request into an execution sequence:

1. make `pdf`, `docx`, and `xlsx` more chunking-friendly,
2. enable `.doc` execution in practice,
3. prepare an implementation decision for `.hwp`.

## Priority Order

### Priority A. Chunk-Boundary Quality

This is the first implementation target because it improves all currently useful formats.

### Priority B. DOC Runtime Activation

This is second because the architecture already exists and the main gap is environment/runtime verification.

### Priority C. HWP Strategy Decision

This is third because there is still no approved executable route.

## Workstream A. Chunk-Boundary Quality

### Goal

Emit reliable, chunking-friendly section starts for `pdf`, `docx`, and `xlsx` while preserving auditability.

### A1. Document current boundary behavior

Tasks:

- gather one or more representative samples for `pdf`, `docx`, and `xlsx`
- inspect current Markdown output and identify where chunk splits should happen
- record false negatives:
  - missing heading boundaries
  - sheet boundaries not surfaced
  - table-title boundaries lost

Outputs:

- sample-driven notes
- before/after candidate cases for regression tests

### A2. Strengthen DOCX heading detection

Tasks:

- keep current Word style-based heading promotion
- add deterministic paragraph-pattern heuristics for heading-like lines
- store why a paragraph was promoted in block metadata

Suggested rule order:

1. `Heading` style match
2. numbered heading pattern
3. Korean section-marker pattern
4. short-title heuristic with conservative thresholds

Files:

- `src/markbridge/parsers/basic.py`
- tests under `tests/unit/`

### A3. Add XLSX sheet-level boundary emission

Tasks:

- emit each worksheet title as a heading block before its table block
- optionally reserve a second pass for table-title detection
- ensure rendered Markdown uses stable `## <sheet name>` boundaries

Files:

- `src/markbridge/parsers/basic.py`
- `src/markbridge/renderers/markdown.py`
- tests under `tests/unit/`

### A4. Preserve machine-readable boundary hints

Tasks:

- add boundary metadata on heading or promoted-heading blocks
- include whether the boundary came from source structure or heuristic promotion
- keep this available for future chunker policies

Suggested metadata:

- `chunk_boundary_candidate`
- `chunk_boundary_reason`
- `chunk_boundary_confidence`
- `chunk_boundary_materialized`

### A5. Validate impact on downstream chunking

Tasks:

- compare output before and after on sample documents
- check whether `##` boundaries align with actual business sections
- check whether aggressive promotion causes over-splitting

Exit criteria:

- `docx` no longer depends only on Word heading styles
- `xlsx` produces at least sheet-level heading boundaries
- no obvious regression in PDF parser-native headings

## Workstream B. DOC Runtime Activation

### Goal

Make `.doc` operational in environments where LibreOffice is available.

### B1. Runtime verification

Tasks:

- confirm `libreoffice` or `soffice` availability in the target environment
- confirm routing enables the `libreoffice` path when available

Files:

- `src/markbridge/routing/runtime.py`
- `src/markbridge/parsers/conversion.py`

### B2. Conversion-path validation

Tasks:

- run sample `.doc` files through conversion
- inspect converted Markdown for heading and table fidelity
- confirm error behavior when conversion fails

### B3. Regression coverage

Tasks:

- add unit/integration tests for:
  - route enabled when LibreOffice exists
  - route held/blocked when missing
  - converted output enters the existing DOCX path cleanly

Exit criteria:

- `.doc` files are executable in supported runtime environments
- failure mode is explicit and traceable when runtime dependency is missing

## Workstream C. HWP Strategy Decision

### Goal

Choose a realistic `hwp` execution route before coding implementation details.

### C1. Candidate path evaluation

Compare:

1. conversion-first path
2. dedicated parser path
3. external converter/service path

Evaluation dimensions:

- on-prem deployability
- licensing and operational constraints
- table fidelity
- heading fidelity
- formula preservation
- ease of mapping into shared IR

### C2. Decision document

Tasks:

- record which route is approved
- record why alternatives were rejected
- define expected runtime dependencies

Exit criteria:

- `hwp` moves from “accepted but unsupported” to a chosen implementation direction

## Suggested Delivery Sequence

1. implement A2 and A3 together
2. add A4 metadata while changing the parser outputs
3. validate A5 on sample outputs
4. enable and verify B1-B3 for `.doc`
5. perform C1 and produce the `hwp` route decision

## Immediate Next Coding Tasks

1. update `DOCX` parsing to promote heading-like paragraphs beyond style-only detection
2. update `XLSX` parsing to emit sheet title heading blocks
3. add tests proving the resulting Markdown now exposes chunk boundaries via `##`
4. add boundary metadata for promoted headings

## Risks

### Over-promotion risk

- too many paragraphs may become headings
- this would hurt chunking more than help it

Mitigation:

- keep heuristics conservative
- validate on real insurance samples
- require regression fixtures before expanding pattern sets

### Conversion-fidelity risk for `.doc`

- successful conversion does not guarantee acceptable structure preservation

Mitigation:

- benchmark converted output, especially headings and tables

### Strategy drift for `.hwp`

- implementation may start before a route is approved

Mitigation:

- force a route decision before parser coding

## Resume Point

Start implementation from:

- `src/markbridge/parsers/basic.py`
- `src/markbridge/renderers/markdown.py`
- `tests/unit/test_pipeline.py`

First code change:

- add deterministic DOCX heading-pattern promotion and XLSX sheet-title heading emission, then lock behavior with tests
