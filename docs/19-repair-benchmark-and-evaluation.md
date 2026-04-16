# 19. Repair Benchmark and Evaluation

## Purpose

This document defines how to evaluate parse quality after corruption detection and repair.
The goal is not to prove that deterministic repair is "as good as" LLM in the abstract.
The goal is to measure:

- which corruption classes can be handled before LLM,
- which cases still require LLM reconstruction,
- and how downstream should trust the parse result.

## Scope

Evaluation applies to corruption classes currently emitted by validation:

- `inline_formula_corruption`
- `table_formula_corruption`
- `formula_placeholder`
- `structure_loss`

## Repair Stages Under Evaluation

Each benchmark case should capture outputs from the following stages:

1. `source markdown`
2. `deterministic repair candidate`
3. `llm repair candidate`
4. `suggested resolved markdown`

The benchmark is not only about string equality. It must also check whether structure and downstream safety were preserved.

## Recommended Case Schema

Store benchmark cases in JSON or JSONL with fields like:

```json
{
  "case_id": "inline-qx-plus-t-L-001",
  "document_format": "docx",
  "corruption_class": "inline_formula_corruption",
  "source_text": "1.3. 해지율(      )에 관한 사항",
  "source_span": "",
  "gold_candidate_text": "1.3. 해지율(q_{x+t}^{L})에 관한 사항",
  "gold_normalized_math": "q_{x+t}^{L}",
  "notes": "Actuarial notation inside heading."
}
```

## Required Evaluation Dimensions

### 1. Mathematical reconstruction accuracy

- `exact_match`
- `normalized_math_match`
- `math_structure_match`

Use `normalized_math_match` when surrounding Korean text may differ slightly but the formula core is correct.

### 2. Local text preservation

- `surrounding_text_preserved`
- `minimal_edit`

The repair should preserve non-math Korean text and avoid rewriting unrelated content.

### 3. Structural safety

- `line_mapping_preserved`
- `table_cell_context_preserved`
- `markdown_safe`

This matters because downstream chunkers will still use source markdown as canonical input.

### 4. Operational quality

- `deterministic_sufficient`
- `llm_required`
- `review_required`

These labels should be decided from observed output, not guessed in advance.

## Suggested Human Review Labels

For each case, a reviewer should assign one of:

- `pass_deterministic`
- `pass_llm`
- `pass_both`
- `fail_both`

And one confidence label:

- `safe`
- `reviewable`
- `fragile`

## How to Compare Deterministic and LLM

### Deterministic is sufficient when

- `normalized_math` is structurally correct,
- surrounding text is preserved,
- and the result does not depend on inferred symbols outside the observed pattern.

Typical examples:

- direct private-use glyph transliteration,
- `q x+t L -> q_{x+t}^{L}`,
- compact table row formula labels.

### LLM is still needed when

- the parser emitted placeholders,
- structure was lost beyond transliteration,
- multiple plausible reconstructions exist,
- or local context from neighboring lines/cells is necessary.

Typical examples:

- `<!-- formula-not-decoded -->`
- broken equations spanning multiple cells or lines
- symbol sequences that need semantic inference, not just glyph mapping

## Current Product Policy

The current service exposes:

- deterministic candidates,
- optional LLM candidates,
- `suggested_resolved_markdown`,
- `downstream_handoff`,
- `parse_evaluation`.

Current downstream policy remains conservative:

- canonical markdown: `source`
- resolved markdown: review companion only

This means the benchmark should optimize for two questions:

1. Did we reconstruct the formula correctly?
2. Did we keep enough traceability for review before canonicalization?

## Recommended Offline Benchmark Flow

1. Build a fixed benchmark set from real anonymized samples.
2. Run parse without LLM.
3. Capture deterministic candidates.
4. Run parse with LLM.
5. Capture LLM candidates and resolved preview.
6. Compare both against gold labels.
7. Record whether deterministic was already sufficient.

## What to Report

At minimum, publish metrics by corruption class:

- total cases
- deterministic exact-match rate
- deterministic structure-match rate
- llm exact-match rate
- llm structure-match rate
- deterministic-sufficient rate
- reviewer-required rate

## Practical Decision Rule

Use the benchmark to define routing thresholds like:

- if deterministic candidate has structured math and benchmark precision is high enough, skip LLM
- otherwise request LLM repair

Do not claim equivalence between deterministic and LLM without measured results on the benchmark set.
