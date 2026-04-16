# 20. Architecture and Delivery Overview

## Goal

MarkBridge converts heterogeneous insurance documents into reviewable markdown and trace artifacts that can be handed to downstream chunking and embedding systems.

The product intentionally separates:

- source-faithful parsing,
- corruption detection,
- repair proposal generation,
- downstream handoff policy.

## End-to-End Flow

1. Source acquisition
2. Inspection and routing
3. Parser execution
4. IR normalization
5. Validation and corruption detection
6. Deterministic repair proposal generation
7. Optional LLM repair proposal generation
8. Suggested resolved markdown preview
9. Downstream handoff packaging
10. UI review and artifact export

## Core Design Principle

The canonical parse output is not automatically rewritten by LLM.

Instead, the system keeps:

- `markdown`
- `repair_candidates`
- `suggested_resolved_markdown`
- `downstream_handoff`
- `parse_evaluation`

This preserves source fidelity while still allowing targeted reconstruction for broken math and table notation.

## Main Runtime Components

### Parsing and routing

- inspection and parser routing choose the executable parser path
- deterministic routing still defines the baseline parser
- LLM routing is optional, but it no longer blindly overrides the baseline parser
- when LLM routing is enabled, MarkBridge can:
  - run the deterministic baseline parser,
  - run the LLM-recommended parser,
  - compare quality signals,
  - keep the baseline unless the recommendation is measurably better

The routing comparison currently emphasizes:

- heading preservation
- line-collapse risk
- average line length
- corruption density

This means "LLM recommended a parser" and "LLM parser was actually selected" are now different states.

### Validation

Validation emits issues such as:

- text corruption
- formula placeholder
- structure loss

These issues are the trigger for repair generation.

### Deterministic repair stage

Deterministic repair currently handles:

- private-use glyph transliteration
- compact actuarial notation rewrites
- table formula normalization

This stage exists to recover common repeated patterns without paying LLM cost.

### LLM repair stage

LLM repair is targeted, not full-document.

It receives:

- issue id
- source text
- source span
- block and line hints
- deterministic candidate
- local markdown context

It returns structured reviewable patch proposals.

When there are many repair targets, the service batches them across multiple LLM calls instead of sending one oversized request.
This reduces malformed JSON and truncation risk for parser outputs such as `docling` where many formula-like targets may be detected at once.

### Resolved preview stage

The service can apply the top-ranked patch per issue to build:

- `suggested_resolved_markdown`
- `suggested_resolved_patches`

This preview is useful for review and downstream experimentation, but it is not the canonical source by default.

### Downstream handoff stage

The handoff layer packages:

- canonical markdown choice
- review requirements
- sidecar repair metadata

Current policy is conservative:

- `policy = dual_track_review`
- `preferred_markdown_kind = source`

## UI Responsibilities

The UI is responsible for making the following relationships visible:

- issue -> evidence
- issue -> repair candidates
- repair candidate -> patch proposal
- patch proposal -> resolved preview
- resolved preview -> downstream handoff policy
- run -> artifacts and evaluation
- baseline parser -> LLM recommendation -> selected parser
- selected repair winner -> rejected competing candidates

The UI is not the source of truth for repair state. The artifact files remain the durable contract.

## Artifact Contract

Each run may emit:

- `repair_candidates.json`
- `llm_formula_repair.json`
- `suggested_resolved.md`
- `suggested_resolved_patches.json`
- `downstream_handoff.json`
- `parse_evaluation.json`

These artifacts are what other teams should consume or archive.

## Quality Model

The service currently exposes an evaluation block with:

- readiness score
- readiness label
- issue counts
- repair counts
- recommended next step

This is a workflow aid, not a mathematical guarantee.

The service also exposes LLM diagnostics for operator review:

- routing baseline parser
- routing recommendation
- routing selected parser
- whether the routing override was actually applied
- routing comparison preview
- repair batch / response diagnostics
- first unresolved formula probe diagnostics
  - whether probe ran
  - whether the probe judged the candidate safe to auto-apply
  - probe confidence
  - region crop image path
  - concise preview of probe rationale and replacement

## Residual Corruption Policy

Two states must remain distinct:

- a line that was historically flagged during validation
- a line that is still unresolved in the final resolved markdown

Today the backend already distinguishes these better than the UI:

- if `final_resolved.md` still contains `<!-- formula-not-decoded -->`, canonical downstream falls back to `source`
- the multimodal formula probe is treated as a review object first
- `apply_as_patch=false` means the probe result must not be materialized into canonical markdown

This means the delivery contract is now:

- canonical downstream markdown may still be `source`
- `final_resolved.md` may remain available as a review artifact
- unresolved formula residues may carry extra probe evidence without being auto-applied

The near-term UI task is to render this distinction explicitly so operators do not confuse:

- "this line once had an issue"
- with
- "this line still contains unresolved formula residue"

## Current Delivery Boundary

MarkBridge is responsible for:

- parsing
- corruption detection
- repair proposal generation
- review-oriented resolved preview
- downstream handoff packaging

MarkBridge is not currently responsible for:

- final approved canonicalization workflow
- downstream chunking
- embedding generation
- retrieval orchestration

## Near-Term Workstreams

### Track A: Repair engine

- expand deterministic glyph mapping
- benchmark deterministic vs LLM
- tighten confidence and escalation policy
- reduce `selected_patch_not_applied` by improving patch anchoring
- stabilize LLM repair for large target sets via batching and smaller prompts

### Track B: UI and evaluation

- make issue handling paths easier to read
- improve review UX for resolved preview and repair traces
- support benchmark-style case review
- expose routing probe-and-gate reasoning clearly in operator UI

### Track C: Documentation and delivery

- maintain handoff contract
- maintain evaluation methodology
- finalize architecture and operator guidance

## Delivery Guidance

When handing this project to another engineer or team, provide:

- this document
- `docs/18-downstream-handoff-contract.md`
- `docs/19-repair-benchmark-and-evaluation.md`
- the latest run artifact directory

That package is sufficient for downstream integration and review-oriented debugging.
