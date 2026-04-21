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
Recommended reading order for current parsing behavior:

- `docs/27-current-parsing-runtime.md`: current code-based parsing flow
- `docs/28-parsing-decision-tree.md`: routing / validation / handoff decision tree
- `docs/30-confluence-parsing-guide.md`: 컨플루언스 게시용 통합 한글 문서
- `docs/24-parsing-policy-and-tuning-guide.md`: parsing policy and tuning guide
- `docs/09-runtime-parser-status.md`: currently installed / enabled parser routes
- `docs/07-parser-capability-registry.md`: wider parser candidate registry and policy posture

## Quick Start
- Install package dependencies from `pyproject.toml`
- Set Azure OpenAI environment variables using `.env.example`
- Ensure AWS access is available through the attached server role for S3-backed parsing
- Run the API with `python3 -m markbridge.api`
- Prefer the managed API scripts for local/server work:
  - `./scripts/run_api_with_log.sh`
  - `./scripts/status_api.sh`
  - `./scripts/tail_api_log.sh`
  - `./scripts/stop_api.sh`
- Long-running parses can be monitored in `.markbridge/logs/markbridge-api.log`
  - Request start: `parse_request ...`
  - Stage progress: `trace_id=... stage=... kind=...`
  - Request end: `parse_completed ...`
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
