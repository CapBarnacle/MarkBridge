# Routing Policy

## Decision Levels

### Level 1: Deterministic Only
Use when structure is simple and parser choice is obvious.

Examples:
- standard DOCX with valid styles
- simple XLSX with low merge complexity
- text-layer PDF with limited tables

### Level 2: Deterministic + LLM Routing
Use only when parser selection is genuinely ambiguous after deterministic rules have already narrowed the executable candidates.

Examples:
- PDF with mixed text/image regions
- parser outputs that are structurally close in expected fidelity
- future parser expansion cases with more than one realistic executable route

### Level 3: Deterministic + Multi-Parser + LLM Reconciliation
Use when structural risk is high.

Examples:
- calculation sheets with merged cells and formulas
- continuation/nested table-heavy documents
- future cases where more than one parser route is executed and outputs must be compared

## Default Rules
- PDF complex layout -> Docling-first
- PDF simple text -> pypdf text-first route
- DOCX structured styles -> python-docx-first
- XLSX merged/formula-heavy -> openpyxl structural route
- DOC -> LibreOffice headless convert -> python-docx route

## Current Practical Policy
In the current project scope, the executable parser candidate set is intentionally small because:
- the environment is primarily on-prem
- paid libraries are not preferred
- OCR is excluded from MVP

As a result, most routing decisions should remain deterministic.
LLM-assisted parser recommendation is not the default path and may have limited value until:
- more than one realistic executable parser exists for the same document family
- the deterministic rules are no longer enough to choose among close alternatives

At the current stage, LLM usage is more defensible for bounded repair or reconciliation than for first-pass parser selection.

## Current Environment Interpretation
Based on the currently installed and enabled toolset:
- PDF routes currently prefer `docling`, with `pypdf` available as a deterministic fallback candidate
- DOCX routes currently collapse to `python-docx` only
- XLSX routes currently collapse to `openpyxl` only
- DOC currently has no enabled conversion route
- HWP currently has no enabled route and should resolve to explicit `hold`

Therefore, the present routing behavior should be interpreted as:
- PDF: deterministic Docling-first execution with OCR disabled and `pypdf` retained as fallback
- DOCX: deterministic single-route execution
- XLSX: deterministic single-route execution
- DOC: unsupported or deferred until conversion tooling is installed and enabled
- HWP: accepted at intake but unsupported for execution

Under this environment, LLM-assisted parser recommendation still has low value for first-pass routing because there are too few materially different enabled alternatives in the active route set.

## Expansion Posture
The current policy is:
- keep the active executable route set narrow
- prefer deterministic routing while the candidate space is small
- preserve the capability registry and runtime status structures so new parser candidates can be added later without changing the routing contract

If deployment or policy constraints are relaxed in the future, parser expansion should happen by:
1. registering the new candidate in the capability registry
2. confirming installation and enablement in runtime status
3. benchmarking source-fidelity impact
4. enabling the route only after deterministic policy is updated
