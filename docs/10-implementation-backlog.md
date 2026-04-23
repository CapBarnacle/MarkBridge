# Implementation Backlog

This backlog translates the current design into an ordered implementation path.

Status note:

- This document is an older backlog snapshot.
- Use [31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md) as the current task list and planning anchor.
- Items below may include work that has since been completed or reframed.

## Guiding Principle
- Keep parser selection quality-first under current runtime constraints.
- Make every pipeline step observable.
- Detect and recover issues as far as possible before downstream handoff.
- Hand downstream the best available final Markdown, while retaining source-faithful artifacts for audit and fallback.

## Current Priority Order

### 1. Routing and Monitoring
- finalize standard trace event flow
- improve parser selection quality for real insurance documents
- connect routing, parser execution, and failures to user-visible monitoring

### 2. Deterministic Inspection
- implement inspection result builders for PDF, DOCX, XLSX, and DOC
- calculate basic complexity and structural indicators
- emit inspection artifacts into trace

### 3. Runtime-Aware Routing
- implement runtime parser status loading
- implement deterministic route selection for the currently enabled parser set
- record candidate filtering and final route rationale in trace

### 4. Parser MVP for Current Environment
- implement `docling`-based PDF path with OCR disabled
- retain `pypdf` as deterministic fallback PDF path
- implement `python-docx`-based DOCX path
- implement `openpyxl`-based XLSX path
- activate `.doc` conversion path automatically when LibreOffice becomes available
- keep `.hwp` on an explicit unsupported `hold` path until a parser is enabled

### 5. Normalize and Render
- normalize parser outputs into shared IR
- render normalized IR into source-faithful Markdown
- export metadata and trace artifacts

### 5b. Filesystem Export
- persist Markdown, trace JSON, issue JSON, and manifest files into a run-specific directory
- keep export paths deterministic under the configured work root

### 5c. Backend CLI
- provide a CLI for local-file and S3 parsing runs
- emit JSON responses compatible with later UI integration

### 6. Validation Execution
- implement concrete validator functions for the initial deterministic rule set
- attach excerpts and location hints to issues
- drive handoff decision from `ValidationReport`

### 7. Repair and Resolution
- define bounded deterministic repair entry points
- call LLM repair automatically for unresolved but repairable issues when enabled
- rank deterministic and LLM repairs per issue
- assemble final resolved Markdown from selected patches
- keep every repair decision trace-visible

### 8. Evaluation and Expansion
- build fixture corpus and regression checks
- benchmark parser fidelity by document family
- benchmark deterministic recovery vs LLM recovery
- add additional parser candidates only after benchmark and enablement review

## Historical Immediate Next Tasks

The section below is retained for historical context.
For current planning, use [31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md).

### Track A. Chunk-Boundary Quality
- improve `docx` heading detection beyond Word style-only promotion
- emit stable `##` boundaries for `xlsx` at least at sheet level
- preserve chunk-boundary candidate metadata so downstream chunkers can use structure hints safely
- compare boundary quality across `pdf`, `docx`, and `xlsx` on real samples

### Track B. DOC Runtime Activation
- activate `.doc` parsing automatically when LibreOffice is available
- validate conversion fidelity for headings and tables on sample insurance documents
- add regression coverage for both available and unavailable conversion-runtime paths

### Track C. HWP Route Decision
- evaluate conversion-first vs dedicated parser vs external adapter approaches
- choose one approved executable route before implementation begins
- keep `.hwp` on explicit `hold` until that decision is made

### Track D. Final Markdown Canonicalization and Review UX
- keep resolved-markdown assembly and downstream handoff policy aligned with current execution
- make final resolved UI distinguish resolved history from still-unresolved residue
- surface the actual downstream Markdown choice explicitly

### Track E. Benchmark and Quality Policy
- add sample-based regression fixtures for PDF, DOCX, XLSX, DOC, and deferred HWP intake behavior
- build anonymized repair benchmark sets from real business documents
- define resolution-grade thresholds for when resolved markdown can become downstream canonical

## Deferred Until Constraints Change
- broad OCR-based fallback recovery
- wide multi-parser full reconciliation on every run
- expansion of the default parser route set beyond the currently enabled environment
