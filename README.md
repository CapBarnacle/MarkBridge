# MarkBridge

MarkBridge is a document-to-Markdown parsing system for the parsing layer of a life-insurance CRM AI Assistant RAG pipeline.

## Goal
Convert PDF, DOCX, XLSX, and DOC documents into Markdown that stays as faithful as possible to the source document, so the output can be passed safely into downstream post-processing for RAG.

## Key Design Principles
- Source fidelity over presentation polish
- Parsing is the current scope; downstream RAG stages are future work
- Deterministic inspection first
- Deterministic parser routing by default
- Selective LLM-assisted orchestration only for ambiguous or high-complexity cases
- Common intermediate representation (IR) before Markdown rendering
- Domain-aware handling for insurance CRM documents
- Future extensibility for HWP

## Initial Scope
- Input: PDF, DOCX, XLSX, DOC
- Output: source-faithful Markdown + metadata JSON + trace/issue artifacts
- Core concerns:
  - merged cells
  - nested tables
  - continuation tables
  - formulas
  - insurance calculation tables
  - preserving retrieval-relevant structure for downstream post-processing

## Non-Goals for MVP
- Perfect visual reproduction
- Full semantic understanding of every table
- HWP implementation in MVP
- Full downstream RAG pipeline implementation

## Project Docs
See `docs/` for architecture, routing policy, WBS, and agent roles.

## Quick Start
- Install package dependencies from `pyproject.toml`
- Set Azure OpenAI environment variables using `.env.example`
- Ensure AWS access is available through the attached server role for S3-backed parsing
- Run the API with `python3 -m markbridge.api`
- Run the frontend with:
  - `cd frontend`
  - `cp .env.example .env.local`
  - `npm install`
  - `npm run dev`
- Run backend parsing from CLI with:
  - `python3 -m markbridge.cli parse-file /path/to/file.docx`
  - `python3 -m markbridge.cli parse-s3 s3://bucket/key.pdf`

Current API surface:
- `GET /health`
- `GET /v1/runtime-status`
- `GET /v1/s3/objects`
- `POST /v1/parse/upload`
- `POST /v1/parse/s3`
