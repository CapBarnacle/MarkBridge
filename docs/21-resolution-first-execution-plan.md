# 21. Resolution-First Execution Plan

Status note:

- This document preserves the resolution-first design context.
- Use [31-active-work-plan.md](/home/intak.kim/project/MarkBridge/docs/31-active-work-plan.md) as the current task list and planning anchor.
- The UI residue and patch anchoring items remain relevant, but priority should be read through the active work plan.

## Purpose

This plan aligns implementation with the clarified project goal:

1. choose the best parser combination for each document,
2. monitor where quality issues happen during parsing,
3. recover as many issues as possible after parsing,
4. hand downstream the final recovered Markdown.

## Current Gap

The current system already supports:

- routing,
- tracing,
- issue detection,
- deterministic repair,
- targeted LLM repair,
- resolved preview generation.

The initial policy gap has now been partially closed:

- `final_resolved_markdown` exists in the API response
- `final_resolved.md` and `final_resolved_patches.json` are persisted
- downstream handoff can now emit `preferred_markdown_kind=resolved`

The remaining gap is execution coverage:

- unresolved repair targets still need broader automatic LLM execution
- unresolved-after-repair accounting still needs richer detail
- patch selection policy still needs smarter candidate ranking and patch anchoring
- multimodal recovery currently works only at whole-page granularity, which is too coarse for formula placeholders
- `final resolved` preview semantics are still ambiguous because historical issue highlighting and actual unresolved residue are not yet visually separated

## Workstreams

### Workstream A. Final Markdown Canonicalization

Goal:
- make the resolved Markdown the primary downstream output when recovery succeeded

Tasks:
- introduce explicit `final_resolved_markdown`
- rank candidate patches by issue
- apply deterministic + LLM patches into a canonical resolved output
- preserve source markdown as fallback and audit artifact
- add run-level metadata indicating:
  - `resolved_available`
  - `resolved_confidence`
  - `unresolved_issue_count`

Exit criteria:
- downstream handoff can prefer resolved Markdown
- final artifact naming is stable

### Workstream B. LLM Recovery Execution

Goal:
- move from “LLM review recommendation” to “LLM recovery execution” for unresolved issue classes

Tasks:
- ensure `llm_requested=true` sends all unresolved repairable targets
- prioritize:
  - `formula_placeholder`
  - `structure_loss`
  - low-confidence deterministic formula corruption
- record why an issue did or did not go to LLM
- record issues still unresolved after LLM
- record which candidate won per issue and why competing candidates were rejected

Exit criteria:
- repair record explains deterministic-only, LLM-repaired, and unresolved cases
- operator can inspect selection winner / rejection reasons without opening artifact JSON

### Workstream C. Monitoring and UI

Goal:
- make the pipeline explain what actually happened and what downstream will receive

Tasks:
- show parser route and parser fallback more explicitly
- show issue counts by status:
  - detected
  - recovered deterministically
  - recovered with LLM
  - unresolved
- show the actual downstream markdown choice
- distinguish:
  - source markdown
  - final resolved markdown
  - unresolved spans
- show which repair candidate became the issue winner and why

Exit criteria:
- a reviewer can tell, without opening JSON artifacts, whether a document is truly downstream-ready

### Workstream D. Benchmark and Policy

Goal:
- define when resolved Markdown is good enough to become canonical

Tasks:
- collect anonymized business-document cases
- measure deterministic vs LLM effectiveness by corruption class
- define thresholds for:
  - resolved-preferred
  - source-fallback
  - manual-review-required

Exit criteria:
- handoff policy is measured, not guessed

## Suggested Parallel Order

1. Start A and B together
2. Start C once A defines final artifact semantics
3. Run D continuously in parallel as evidence-building

## Immediate Next Implementation Steps

1. Tighten selection policy so generated LLM candidates beat deterministic baselines only when they also apply cleanly
2. Improve patch anchoring for selected winners that currently end as `selected_patch_not_applied`
3. Add tests for deterministic + LLM mixed repair on one document
4. Add placeholder materialization gating so `final_resolved.md` cannot be treated as fully recovered while placeholders remain
5. Replace whole-page multimodal formula probe with region-crop probe for the first unresolved placeholder
6. Split `final resolved` UI highlights into:
   - previously-flagged-but-resolved
   - still-unresolved-in-final
7. Define how unresolved `formula-not-decoded` residues are handed downstream:
   - source-only canonical
   - markdown + sidecar residual objects
   - manual-review block
8. Verify PDF live runs under the new resolved-preferred policy
9. Measure unresolved-by-reason shifts after the new anchoring/policy changes

Status note:
- selection fallback to the next applicable candidate is now implemented
- recent live PDF run still shows `selected_patch_not_applied=3`, so patch anchoring is the next concrete bottleneck
- routing is now baseline-vs-recommendation probe based, not direct LLM override
- recent live PDF run confirms `pypdf` recommendation can be rejected while keeping `docling`
- batched LLM repair on the retained `docling` baseline now generates substantial candidates again
- first multimodal formula probe now exists as `probe-first-formula`
- the first live probe matched page 2 successfully, but whole-page image guidance produced a heading false positive instead of a formula reconstruction
- region crop is now implemented and materially improved the probe: it now returns formula-like reconstruction attempts rather than just heading text
- however the latest first-placeholder result is still `apply_as_patch=false`, so probe output is currently review-only evidence, not safe canonical markdown material
- canonical downstream gating for placeholder residue is now implemented, but UI semantics for unresolved residue are still unfinished

## Morning Resume Point

Tomorrow, resume from:

- [`src/markbridge/api/service.py`](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)
- [`src/markbridge/api/models.py`](/home/intak.kim/project/MarkBridge/src/markbridge/api/models.py)
- [`frontend/src/App.tsx`](/home/intak.kim/project/MarkBridge/frontend/src/App.tsx)
- [`docs/21-resolution-first-execution-plan.md`](/home/intak.kim/project/MarkBridge/docs/21-resolution-first-execution-plan.md)

The first concrete code change should be:
- separate `final resolved` line styling for resolved-vs-unresolved residue, then decide whether unresolved formula probe objects should travel as downstream sidecars
