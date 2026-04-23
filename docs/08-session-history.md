# Session History

This document is the restart anchor for interrupted MarkBridge work.
It is intentionally biased toward "what is true now" rather than preserving every historical intermediate state.

## Current Planning Anchor

- Active work planning now lives in [docs/31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md).
- Use that document first when deciding the next task.
- Treat older plan documents as historical context unless `docs/31-active-work-plan.md` explicitly points to them as active detail.

## Resume Prep on April 23, 2026

- Current branch: `feature/document-ir-rag-handoff`.
- Branch base/current docs commit: `7bcc002 Add active work plan and IR chunking readiness docs`.
- At the time this handoff note was written, `HEAD`, `main`, and `origin/main` all pointed to `7bcc002`.
- Working tree was clean before this history update.
- Pre-existing non-doc WIP was intentionally preserved in git stash:
  - `stash@{0}: On document-ir-rag-handoff: pre-existing non-doc changes before document-ir-rag-handoff`
- Do not pop that stash unless intentionally resuming the older non-doc WIP.

Current restart docs added in the latest parsing/RAG planning pass:

- [docs/31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md)
- [docs/32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md)

Current architectural decision:

- `DocumentIR` generation is the shared parsing core.
- After `DocumentIR`, the pipeline splits into two branches.
- Branch A preserves the existing Markdown rendering, line map, canonical block JSON, and `/exports/parse-markdown` API.
- Branch B is the new internal RAG pipeline path: `DocumentIR` to chunk source, chunking, embedding/indexing, and retrieval.
- Own RAG chunking should not parse canonical Markdown as its primary input.
- Parser-known source facts should be preserved in `DocumentIR`; chunking-derived facts should be created in the chunking model.
- Canonical Markdown remains necessary for external delivery, audit, UI, and existing API compatibility.

Next work should start here:

- Run a `DocumentIR` chunking readiness audit.
- Create representative `DocumentIR` dumps for PDF, DOCX, XLSX, DOC, and HWP routes where available.
- Build a coverage matrix for block kinds, heading metadata, table metadata, and source span coverage.
- Verify chunk text can be generated from `DocumentIR` without reparsing Markdown.
- Decide P1 IR enrichments: stable `parser_block_ref`, broader `BlockIR.source` coverage, normalized heading metadata, table `header_depth`/caption/title, and validation issue links.

## Resume Prep on April 23, 2026 After IR Enrichment and BMT Audit

- The work branch is still `feature/document-ir-rag-handoff`.
- Current working tree is no longer clean. There are uncommitted code/doc changes for the first `DocumentIR` enrichment pass plus a new audit CLI path.
- Pre-existing unrelated WIP is still preserved only in `stash@{0}` and must not be mixed with the current IR/chunking work.

Implemented in this pass:

- `DocumentIR` first-pass enrichment:
  - `BlockIR.parser_block_ref`
  - `BlockIR.heading_level`
  - `TableBlockIR.caption`
  - parser/document metadata normalization
  - broader `BlockIR.source` population for PDF page, XLSX sheet/row range, and single-page markdown-derived routes
  - table `header_depth`
  - table title/caption hint from preceding heading or short caption-like paragraph
- Markdown rendering still preserves the existing export/API contract based on `block-{index}` refs.
- New audit command was added:
  - `PYTHONPATH=src python3 -m markbridge.cli audit-document-ir ...`

New/updated restart docs:

- [docs/31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md)
- [docs/32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md)
- [docs/33-bmt-document-ir-audit.md](/home/intak.kim/project/MarkBridge/docs/33-bmt-document-ir-audit.md)

New audit code/tests added in this pass:

- [src/markbridge/audit/document_ir.py](/home/intak.kim/project/MarkBridge/src/markbridge/audit/document_ir.py)
- [src/markbridge/audit/__init__.py](/home/intak.kim/project/MarkBridge/src/markbridge/audit/__init__.py)
- [tests/unit/test_document_ir_audit.py](/home/intak.kim/project/MarkBridge/tests/unit/test_document_ir_audit.py)

BMT sample audit was executed from:

- `s3://rag-580075786326-ap-northeast-2/bmt/`

Audit artifacts were written locally under:

- [`.markbridge/audits/document-ir/2026-04-23-bmt/`](/home/intak.kim/project/MarkBridge/.markbridge/audits/document-ir/2026-04-23-bmt)

Key audit conclusions:

- `parser_block_ref` coverage is 100% on all sampled formats.
- `heading_level` coverage is 100% on heading blocks for all sampled formats.
- `table_header_depth` and `table_title` are effectively ready for chunking input.
- XLSX currently has the best `source` coverage.
- The biggest remaining IR gaps are:
  - PDF/DOCX/DOC block-level source span
  - table page range
  - validation issue to chunk join rules

Current implementation truth after this pass:

- `DocumentIR` is now good enough to begin `ChunkSourceDocument` design and initial chunking work.
- The correct next step is no longer "more generic parsing improvement first."
- The correct next step is:
  - design `DocumentIR -> ChunkSourceDocument`
  - define validation issue / quality flag joins
  - only then add narrowly targeted IR/source-span improvements where the handoff model proves they are needed

Current uncommitted work to preserve when resuming:

- code changes in:
  - `src/markbridge/shared/ir.py`
  - `src/markbridge/parsers/basic.py`
  - `src/markbridge/renderers/markdown.py`
  - `src/markbridge/cli.py`
  - `src/markbridge/audit/`
- tests in:
  - `tests/unit/test_markdown_renderer.py`
  - `tests/unit/test_pipeline.py`
  - `tests/unit/test_document_ir_audit.py`
- docs in:
  - `docs/31-active-work-plan.md`
  - `docs/32-document-ir-chunking-readiness.md`
  - `docs/33-bmt-document-ir-audit.md`

Verification already run in this pass:

- `pytest -q tests/unit/test_markdown_renderer.py tests/unit/test_validators_execution.py tests/unit/test_pipeline.py -k "not test_doc_pipeline_is_held_when_no_route_exists"`
- `pytest -q tests/unit/test_document_ir_audit.py`

Known caveat:

- `test_doc_pipeline_is_held_when_no_route_exists` remains environment-sensitive because the current runtime has `libreoffice` enabled in this machine, so that old expectation is not a reliable restart assumption.

## Resume Prep on April 16, 2026

- Reconfirmed current orchestration flow in `src/markbridge/api/service.py`:
  - routing compare-and-select
  - deterministic + optional LLM repair candidate generation
  - `final_resolved_markdown` assembly
  - `resolution_summary` accounting
  - conditional downstream handoff selection
- Reconfirmed current frontend continuation point in `frontend/src/App.tsx`:
  - `Source` / `Final resolved` preview toggle already exists
  - current highlight path still does not visually separate:
    - historically flagged but now resolved lines
    - placeholder residue still unresolved in final resolved markdown
- Reconfirmed active API/frontend types in `src/markbridge/api/models.py` and `frontend/src/types.ts`:
  - `final_resolved_markdown`
  - `final_resolved_patches`
  - `resolution_summary`
  - `llm_diagnostics`
  - `downstream_handoff.final_resolved_available`
- Documentation drift still exists:
  - `docs/17-resume-brief.md`, `docs/21-resolution-first-execution-plan.md`, and `src/markbridge/api/service.py` reflect the current conditional source/resolved handoff model
  - older examples or notes in surrounding docs may still read like the fixed `dual_track_review` / source-first policy, so verify against current code when in doubt

## Current Baseline

- MarkBridge is a parsing-layer product for a life-insurance CRM AI Assistant pipeline, not a full downstream RAG system.
- The system now covers parsing, tracing, issue detection, deterministic repair, optional LLM repair, resolved-markdown assembly, and downstream handoff packaging.
- The primary durable artifacts are no longer just source Markdown and trace. They now include reviewable repair and resolved-output sidecars.
- Artifact storage should no longer rely on `/tmp/markbridge` as the primary durable location.
  - current preferred work root is `MARKBRIDGE_WORK_DIR=/home/intak.kim/project/MarkBridge/.markbridge/runs`
  - downstream-oriented handoff now benefits from a single canonical markdown file in each run directory
- OCR remains out of scope for MVP. The active `docling` PDF path must continue running with OCR disabled.
- Routing is runtime-aware and policy-aware. Only installed, enabled, and allowed parsers may be selected.
- Validator output remains the canonical source of parse-quality issues.
- Handoff policy is now conditional rather than fixed-source-only:
  - if recovery succeeded cleanly, downstream may prefer `final_resolved.md`
  - if unresolved placeholder residue remains, canonical downstream falls back to source Markdown

## Authoritative Restart Docs

Read these first when resuming:

- `docs/31-active-work-plan.md`
- `docs/30-confluence-parsing-guide.md`
- `docs/24-parsing-policy-and-tuning-guide.md`
- `docs/27-current-parsing-runtime.md`
- `docs/28-parsing-decision-tree.md`

Important note:

- Some docs still contain older policy snapshots.
- When docs disagree about work priority, trust `docs/31-active-work-plan.md`.
- When docs disagree about current parsing runtime behavior, trust current code plus `docs/27-current-parsing-runtime.md`, `docs/28-parsing-decision-tree.md`, and `docs/30-confluence-parsing-guide.md`.
- In particular, older `dual_track_review` / source-only descriptions are historical, not universally current.

## Session Decisions So Far

### 1. OCR stays out of scope for MVP

- No OCR substitution path should be treated as the normal recovery mechanism.
- Missing text layers or formula placeholders may be surfaced as degraded or unresolved states instead of being silently reconstructed.

### 2. Trace is a product artifact

- Trace data is meant for operator review, not only internal logging.
- The UI should explain where quality degraded, which parser path was used, and which recovery steps ran.

### 3. Validation detects issues before repair

- Deterministic validation remains the first detector for text corruption, malformed formulas, structure loss, and suspicious table output.
- LLM should only act after detection, as a bounded repair worker or recommendation layer.

### 4. Routing is compare-and-select, not blind LLM override

- Deterministic routing still establishes the baseline parser.
- If LLM routing recommends another parser, MarkBridge may run both baseline and recommendation, compare quality signals, and only override when the candidate is measurably better.
- This keeps `routing_recommendation` distinct from `routing_selected_parser`.

### 5. Source fidelity and resolved output now coexist

- Source-faithful Markdown is still preserved for audit, traceability, and fallback.
- The system can now assemble `final_resolved.md` from deterministic and LLM repair patches.
- Downstream choice depends on recovery quality and unresolved residue, not on a blanket source-only rule.

### 6. Repair is patch-based and reviewable

- Repair candidates are emitted per issue with explicit patch proposals.
- Candidate selection is issue-local and records winner / rejection reasons.
- LLM repair is targeted, batched, and structured rather than full-document rewriting.

### 7. Placeholder residue is a hard gating signal

- `<!-- formula-not-decoded -->` must be treated separately from historically detected issues that were later resolved.
- If placeholder residue remains in the final resolved output, canonical downstream must fall back to source Markdown unless an explicit acceptance policy is added later.

## Progress Snapshot

- Backend API, CLI, routing, tracing, exporter, validator, repair generation, and resolved-output assembly are implemented.
- Active runtime routes:
  - PDF: `docling` baseline, `pypdf` comparison/fallback
  - DOCX: `python-docx`
  - XLSX: `openpyxl`
  - DOC: `libreoffice` conversion route plus `antiword` text fallback scaffold exist, but current runtime still lacks the required system tools
  - HWP: `hwp5txt` text-route scaffold now exists, but current runtime still lacks the command so execution remains `hold`
- `preferred_markdown` handling now carries explicit Markdown line numbers so preview highlight mapping is more stable.
- Runtime status surfaces now expose `supported_formats` and `route_kind`, so `antiword` degraded fallback and `hwp5txt` text-route status are visible in both API and CLI output.
- `antiword` / `hwp5txt` 같은 degraded text routes are now forced to `degraded_accept` handoff even when validation itself is clean, and the route kind is surfaced in handoff metadata plus API notes.
- API responses now include:
  - `repair_candidates`
  - `suggested_resolved_markdown`
  - `suggested_resolved_patches`
  - `final_resolved_markdown`
  - `final_resolved_patches`
  - `resolution_summary`
  - `downstream_handoff`
  - `evaluation`
  - `llm_diagnostics`
- Repair taxonomy now explicitly covers:
  - `inline_formula_corruption`
  - `table_formula_corruption`
  - `formula_placeholder`
  - `structure_loss`
- Deterministic formula repair is stronger than before and can normalize common actuarial notation patterns.
- LLM repair execution now runs in batches across large target sets instead of sending oversized single requests.
- The first unresolved-placeholder multimodal probe now exists as `probe-first-formula`.
- The probe improved after switching from whole-page context to a region crop, but current results are still review-only unless `apply_as_patch=true`.
- DOCX parsing heuristics were tightened again for real operator examples:
  - closed-number headings like `1)`, `2)`, `3)` are promoted to Markdown headings
  - single-column DOCX layout tables are now preserved as boxed note-like Markdown blocks instead of being fully flattened
  - DOCX horizontal merged-cell duplicates such as repeated `접수방법 | 접수방법` are normalized away before table rendering
  - contextual circled-number section titles such as `① 보험계약조회 및 보험료납입` are promoted only when section context is strong enough

## Current Implementation Truths

- The main orchestration truth now lives in `src/markbridge/api/service.py`.
- Downstream handoff currently supports these practical states:
  - `source_only`
  - `dual_track_review`
  - `resolved_preferred`
  - `resolved_with_fallback`
- Canonical downstream may be `resolved` when recovery succeeded.
- Canonical downstream must revert to `source` when unresolved placeholder residue remains.
- Each run can now expose a single downstream-facing canonical markdown file named from the original full source filename, such as `sample.docx-1.md`, while still preserving `result.md` and `final_resolved.md` internally.
- Routing probe metrics currently emphasize:
  - heading preservation
  - long-line collapse risk
  - average line length
  - corruption density
- Resolution accounting distinguishes:
  - deterministic recovery
  - LLM recovery
  - unresolved after repair
  - `selected_patch_not_applied`

## Verified Local State

Verified on April 16, 2026:

- `pytest -q` passes
- Current local result: `83 passed, 1 warning`
- Warning observed:
  - `docling` emits a deprecation warning around table image generation in `standard_pdf_pipeline.py`

## Main Bottlenecks Now

### 1. Final-resolved UI semantics are still incomplete

- The UI still needs clearer visual separation between:
  - previously flagged but now resolved spans
  - still unresolved residue in `final_resolved`
- This is the highest-value near-term task because backend semantics are ahead of the frontend explanation.

### 2. Patch anchoring remains a quality risk

- Candidate generation is much better than before.
- The remaining failure mode is often applicability and anchoring, not the absence of a candidate.
- `selected_patch_not_applied` is the key signal to reduce next.

### 3. Probe outputs are not yet canonical-safe

- The region-crop formula probe can produce better reconstruction attempts.
- The latest policy still treats probe outputs as evidence first, not automatically materialized canonical Markdown, unless explicitly marked safe.

### 4. Some docs still reflect older policy states

- Resume work should not assume every Markdown doc is equally current.
- Any new doc edits should converge toward the current source/resolved conditional handoff model.

### 5. DOCX layout fidelity still needs case-by-case tuning

- The latest live DOCX regressions should now use durable runs under `.markbridge/runs/...` first, not `/tmp/markbridge/...`.
- Two concrete parser-quality issues were identified from that run:
  - boxed caution sections under headings were being flattened into plain paragraphs
  - horizontally merged DOCX table cells could duplicate labels like `접수방법`
- Current code now preserves single-column layout tables as note-like blocks and suppresses horizontal-merge duplicates before rendering.
- Recent live evidence also established a positive circled-number heading case in `300138_라이프앱가능업무.docx` and a control DOCX in `300233_계약관계자변경.docx`.
- Similar DOCX forms may still surface additional layout heuristics that need targeted regression tests.

### 6. Parser-policy changes now require recent same-format regression checks

- Any parsing-rule change must be validated against:
  - the motivating document,
  - at least one recent same-format control document,
  - updated unit tests with positive and negative cases.
- Preferred evidence root is `.markbridge/runs/<run_id>/`.
- For DOCX tuning, current practical anchors are:
  - positive case: `300138_라이프앱가능업무.docx`
  - control case: `300233_계약관계자변경.docx`
- Validation must leave behind the compared run paths and the observed structural deltas in docs, not only an informal verbal claim.

## Recommended Resume Point

Resume from these files first:

- `src/markbridge/api/service.py`
- `src/markbridge/api/models.py`
- `frontend/src/App.tsx`
- `frontend/src/types.ts`
- `docs/21-resolution-first-execution-plan.md`

First concrete task:

- separate `final resolved` line styling so the UI clearly distinguishes resolved history from still-unresolved residue, then decide how unresolved formula-probe objects should travel as downstream sidecars

## Practical Next Steps

1. Inspect the current `final resolved` rendering path in the frontend and split highlight semantics into resolved vs unresolved residue.
2. Confirm whether unresolved formula probe artifacts should be shown only in review UI or also shipped as downstream sidecars.
3. Tighten patch anchoring for the remaining `selected_patch_not_applied` cases.
4. Add regression coverage for mixed deterministic + LLM repair selection and unresolved-residue gating.
5. Update older docs that still imply a fixed source-only canonical policy.
6. Keep `docs/08-session-history.md` and `docs/15-ui-api-contract.md` aligned with `service.py` whenever downstream handoff semantics change.

## Files To Reopen First

- `docs/17-resume-brief.md`
- `docs/21-resolution-first-execution-plan.md`
- `src/markbridge/api/service.py`
- `src/markbridge/api/models.py`
- `frontend/src/App.tsx`
- `frontend/src/types.ts`

## Useful Commands

```bash
pytest -q
```

```bash
python3 -m markbridge.cli runtime-status
```

```bash
python3 -m markbridge.cli parse-file /path/to/file.pdf --llm
```

```bash
python3 -m markbridge.cli probe-first-formula /tmp/markbridge/<run_id> --llm
```

## Suggested Restart Prompt

If a later session needs to resume quickly, use this prompt:

Continue MarkBridge from `docs/08-session-history.md`. Treat `src/markbridge/api/service.py` as the current orchestration source of truth. Preserve product boundaries: parsing, tracing, issue detection, deterministic repair, optional LLM repair, resolved-output assembly, and downstream handoff. OCR remains out of scope. Routing must remain baseline-first with compare-and-select override. Keep source Markdown for audit and fallback, but allow resolved Markdown as canonical downstream output only when recovery succeeded and no unresolved placeholder residue remains.
