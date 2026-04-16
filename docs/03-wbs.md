# Work Breakdown Structure

## Phase 0. Foundation
- define project charter
- define architecture spec
- define repo structure
- define agent model

## Phase 1. Core Data Model
- define IR schema
- define parser base interface
- define inspection report model
- define routing decision model

## Phase 2. Deterministic Inspection and Routing
- implement inspectors for PDF/DOCX/XLSX/DOC
- define parser capability registry
- implement routing rules
- implement complexity scoring

## Phase 3. Parser MVP
- PDF parser pipeline
- DOCX parser pipeline
- XLSX parser pipeline
- DOC conversion pipeline

## Phase 4. Complex Structure Handling
- merged cell resolver
- nested table model
- continuation table merger
- formula extraction model

## Phase 5. Rendering and Validation
- Markdown renderer
- metadata exporter
- validation checks
- integration tests

## Phase 6. Selective LLM Orchestration
- LLM router prompt
- reconciliation prompt
- benchmark comparison with deterministic baseline

## Phase 7. Hardening
- fixture expansion
- regression evaluation
- docs refinement
- Codex workflow refinement