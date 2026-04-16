# Project Charter

## Project Name
MarkBridge

## Objective
Build the parsing layer for a life-insurance CRM AI Assistant RAG pipeline.

The primary objective is to convert source documents into Markdown with the highest practical fidelity to the original document so the output can be handed off to downstream post-processing with minimal structural loss.

## In Scope
- PDF, DOCX, XLSX, DOC ingestion
- Common IR design
- Markdown rendering
- Metadata export
- Trace and issue export
- Deterministic inspection and routing
- Selective LLM-assisted orchestration
- Handling of merged cells, nested tables, continuation tables, and formulas
- Preserving retrieval-relevant structure for downstream processing

## Out of Scope (MVP)
- Full HWP implementation
- Pixel-perfect layout reproduction
- End-user UI
- Production-grade distributed execution
- Full downstream RAG pipeline implementation beyond parsing outputs

## Success Criteria
- Stable conversion for target document families
- High source fidelity in Markdown output
- Structural preservation of headings, tables, notes, and formulas
- Low-loss handoff into downstream post-processing
- Reproducible parser selection
- Benchmarkable quality metrics

## Domain Assumption
Primary target documents are insurance CRM-related materials including product guides, operational forms, premium calculation sheets, summary reports, and policy-related structured documents.
