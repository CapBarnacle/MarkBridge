# Architecture Specification

## 1. Overview
MarkBridge uses a hybrid architecture:
1. Deterministic inspection
2. Deterministic routing by default
3. Optional LLM-assisted routing/reconciliation for complex cases
4. Common IR normalization
5. Validation and issue detection
6. Trace-oriented monitoring for step-by-step visibility
7. Markdown + metadata export

MarkBridge is the parsing layer of a life-insurance CRM AI Assistant RAG system.
Its responsibility is to produce the best available final Markdown for downstream use by combining:
- optimal parser selection
- step-level monitoring
- issue detection
- bounded post-parse recovery

## 2. Pipeline
Input Document
-> Deterministic Inspection
-> Routing Policy Engine
-> Parser Pipeline Execution
-> IR Normalization
-> Validation / Issue Detection
-> Deterministic Repair
-> LLM Repair Fallback
-> Resolution / Final Markdown Assembly
-> Trace + Metadata Export

## 3. Deterministic Inspection
Inspection extracts machine-observable features without using an LLM.

Examples:
- file format
- page count / sheet count
- text layer availability
- image ratio
- table candidate count
- merged cell count
- formula ratio
- nested table indicators
- layout variance

OCR necessity may still be estimated for diagnostic purposes, but OCR execution is out of scope for MVP and must not be used as a recovery path.

## 4. Routing Policy
The routing policy engine selects parser/tool combinations using:
- file format
- inspection features
- parser capability registry
- runtime availability registry
- complexity thresholds
- hard trigger rules

Routing decisions must be limited to parser/tool combinations that are both:
- supported by project policy
- installed and available in the current runtime environment

The routing contract should remain stable even if parser candidates are added later.
Future parser expansion should primarily require:
- adding capability entries
- updating runtime status
- adding or enabling parser implementations
- extending deterministic routing rules where justified

It should not require redesigning the overall pipeline shape.

## 5. LLM Usage Policy
LLM is not the default parser.
LLM is used selectively for:
- ambiguous parser selection
- complex structural interpretation
- reconciliation across multiple parsing outputs
- bounded repair of detected structural issues that deterministic recovery could not resolve well enough

LLM is not used for:
- OCR substitution
- unsupported library recommendation in executable routes
- ungrounded text restoration
- arbitrary table structure reconstruction

LLM recommendations must be benchmarked against deterministic baselines.
Deterministic validators should detect issues first, deterministic repair should run before LLM, and LLM-based repair should be used to maximize final downstream quality where bounded recovery is still needed.

## 6. Intermediate Representation (IR)
All parsers convert their output into a shared IR.

Core block types:
- heading
- paragraph
- list
- table
- formula
- note
- warning
- image_ref
- footer

Table-specific fields:
- table_id
- title
- page_range
- header_depth
- merged_cells
- nested_regions
- continuation_of
- semantic_type
- confidence

The IR must preserve enough source and structural context for downstream validators, trace views, and optional repair steps.

## 7. Validation and Traceability
Validation is a first-class pipeline stage.

The system must detect:
- text corruption or broken character patterns
- malformed or incomplete table structures
- missing or weak image references
- suspicious document structure transitions

Validation should produce canonical issue records with:
- stable issue identifier
- issue code and severity
- location hints
- human-readable evidence excerpts
- repairability flag
- disposition status for follow-up handling

The initial deterministic validator set should prioritize rules that directly affect downstream RAG handoff quality:
- empty or near-empty parse output
- broken character patterns
- corrupted table structure
- weak image references
- suspicious heading or block-order transitions

Validation output should feed a quality gate that determines whether downstream handoff is:
- accepted
- accepted with degraded status
- held for manual review or later repair

Trace-oriented monitoring is also a first-class concern.
Each pipeline stage should emit step-level events so users can inspect:
- which component ran
- what was selected
- what artifacts were produced
- where warnings or failures occurred
- which issues were detected
- whether any repair attempt was accepted or rejected

The implementation should follow a standard trace flow spanning:
- ingest
- inspection
- routing
- parsing
- normalization
- validation
- optional repair decision
- rendering
- export

The initial trace model should minimally support:
- a per-run trace identifier
- stage and event kind
- current status
- component name
- timestamp
- message summary
- artifact references
- issue snapshots
- lightweight event metadata for UI display
- human-readable excerpts for suspicious content or malformed structure

Trace output should help users understand the failure without opening raw internal data first.
For issue-heavy stages, the UI-facing trace payload should prefer:
- short readable excerpts
- location hints such as page, sheet, or block identifier
- highlighted suspicious text or structure markers
- concise explanation of why the content was flagged

## 8. Output
Primary:
- final resolved Markdown for downstream chunking and embedding

Secondary canonical support:
- source-faithful Markdown for audit, diff, and fallback

Secondary:
- metadata JSON
- trace JSON
- issue report JSON
- optional table/formula sidecar JSON

The primary quality target is not visual beauty. It is maximizing source-grounded recovery so later chunking, indexing, retrieval, and grounding stages can rely on the final output with traceable evidence.

## 9. Library Strategy
- PDF: Docling first, pypdf as lightweight support/fallback path
- DOCX: python-docx first
- XLSX: openpyxl first
- DOC: convert-to-docx then parse
- HWP: planned extension

Executable routing candidates are restricted to libraries that are already installed and enabled in the current environment.
Uninstalled libraries may be documented as future options, but they must not appear in active runtime decisions.

## 10. Extension Strategy
Format parsers and domain normalization must remain separate.
This allows future HWP support without rewriting the domain layer.

If the parsing layer proves stable, the broader RAG pipeline may be expanded in later phases, but that work is outside the current implementation scope.

The same principle applies to parser growth under relaxed constraints.
The system should keep a narrow default route set today, while preserving registry- and contract-based extension points so additional parser candidates can be introduced later with minimal architectural churn.
