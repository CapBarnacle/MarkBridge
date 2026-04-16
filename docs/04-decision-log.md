# Decision Log

## D-001: Hybrid architecture
We use deterministic inspection and deterministic routing by default, with selective LLM assistance only for ambiguous or high-complexity cases.

## D-002: LLM is not the default parser
LLM is treated as a planner/reviewer, not as the primary parser.

## D-003: Common IR before Markdown
All format-specific parsing must normalize into a shared IR before rendering.

## D-004: Markdown plus metadata
Primary output is Markdown, but metadata JSON is retained for structural preservation and future downstream use.

## D-005: Library baseline
- PDF: Docling-first
- DOCX: python-docx-first
- XLSX: openpyxl-first
- DOC: convert then parse

## D-006: Insurance CRM focus
MVP is optimized for insurance CRM documents, especially complex tables and formulas.

## D-007: HWP planned, not MVP
HWP support is a planned extension point but not an MVP deliverable.

## D-008: Python src-layout foundation
The initial implementation scaffold uses a Python `src/markbridge` package with clean module boundaries for `inspection`, `routing`, `parsers`, `normalize`, `renderers`, `validators`, and `shared`.

Shared contracts needed across boundaries are defined as stdlib-only typed dataclasses/enums first, while parser-specific logic remains out of scope until deterministic inspection and routing are implemented.

## D-009: OCR excluded from MVP
OCR-based parsing and OCR-based recovery are excluded from MVP scope.

Inspection may retain diagnostic signals related to text-layer absence or OCR necessity, but routing and repair must not invoke OCR paths.

## D-010: Trace-oriented monitoring is a first-class product feature
MarkBridge must expose step-by-step parsing progress and failures so users can inspect where a document was routed, parsed, normalized, validated, and possibly repaired.

This is not only an operational logging concern. Trace data is a user-facing artifact intended to support debugging, trust, and iterative tuning of the pipeline.

## D-011: Deterministic detection first, bounded LLM repair second
Detection of parse-quality problems should be deterministic by default and live in validation/quality checks.

LLM usage is acceptable only for bounded post-processing tasks such as structural reconciliation or issue-targeted repair, and only after a deterministic issue has been detected.

## D-012: Runtime-available libraries only for executable routing
Parser selection, including any LLM-assisted recommendation, must be constrained to tools that are both supported by project policy and actually installed or enabled in the current runtime environment.

Libraries not available in the runtime may be recorded as future options, but must not be returned as active executable routes.

## D-013: Tracing starts as a generic event model
The first tracing implementation uses a generic stage/event/artifact/issue model instead of stage-specific payload classes.

This keeps tracing independent from parser, validator, and renderer internals while still supporting user-visible step-by-step monitoring.

## D-014: Tracing must carry user-readable evidence
Tracing should not only record that an issue happened. It should also carry compact, human-readable evidence such as suspicious text excerpts, location hints, and highlighted fragments where possible.

This is required so the trace UI can explain parsing failures and degraded outputs without forcing users to inspect raw internal artifacts first.

## D-015: Validators own canonical issue records
Trace views may show summarized issue snapshots, but the source of truth for parse-quality problems belongs to validators.

Validators should emit canonical issue records that can later be summarized for trace display, metadata export, and optional repair decisions.

## D-016: MarkBridge is the parsing layer of the target RAG system
MarkBridge is being built as the parsing component for a life-insurance CRM AI Assistant RAG workflow, not as a general-purpose end-to-end RAG system.

Its immediate responsibility is to hand off high-fidelity Markdown and supporting metadata to later post-processing stages. Broader RAG pipeline expansion remains future work.

## D-017: Current parser selection should remain mostly deterministic
Given the current on-prem constraint, paid-library avoidance, and relatively small executable parser set, most parser selection should remain deterministic.

LLM-assisted parser recommendation is a secondary mechanism that becomes more valuable only when the executable candidate set grows or when multiple realistic routes are close in expected fidelity.

## D-018: Additional parser candidates may be tracked without entering the default route set
The capability registry may include secondary, experimental, and policy-review-required tools beyond the current baseline.

This does not mean they participate in routing by default. The default route set remains intentionally narrow until a candidate is benchmarked, installed, and explicitly enabled.

## D-019: Routing behavior depends on the actual installed environment snapshot
The capability registry defines what could be used in principle, but the effective route set is determined by what is currently installed and enabled.

At the current snapshot, effective routing is single-route for DOCX and XLSX, limited to `pypdf` for PDF, and unavailable for `.doc` conversion paths.

## D-020: Keep today’s route set narrow, but keep parser expansion cheap
The project should optimize for a narrow and deterministic active route set under current constraints, while preserving extension points that make future parser addition straightforward.

New parser candidates should be introduced through registry entries, runtime enablement, benchmarking, and rule updates rather than by changing the core pipeline architecture.

## D-021: Validator rules should optimize for downstream handoff quality first
The first validator rule set should focus on conditions that most directly threaten reliable downstream post-processing for RAG.

This means empty output, broken text, corrupted table structure, weak image anchoring, and suspicious structural transitions take priority over cosmetic Markdown concerns.

## D-022: Standard trace flow should be fixed before broader implementation
Trace is a full-pipeline execution view, not only a validation log.

Implementation should therefore follow a standard stage/event flow so inspection, routing, parsing, normalization, validation, repair decisions, rendering, and export are all trace-visible in a stable order.

## D-023: Downstream handoff must be controlled by an explicit quality gate
Validation should not stop at issue generation. It must also drive a clear downstream handoff decision.

The initial handoff states are:
- accept
- degraded_accept
- hold

## D-024: Active PDF baseline is Docling without OCR
When `docling` is available, it becomes the preferred active PDF parser route ahead of `pypdf`.

This active `docling` route must run with OCR disabled so the implementation stays consistent with the project's OCR exclusion policy. `pypdf` remains the deterministic fallback path for simpler or constrained environments.

## D-025: HWP enters the pipeline as an explicit unsupported route
`.hwp` files should not be rejected at intake solely because implementation is pending.

They should enter the same traceable pipeline surface as other document types, then resolve to an explicit `hold` decision until an enabled parser route exists.
