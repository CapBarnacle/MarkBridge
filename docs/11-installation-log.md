# Installation Log

This document records project dependency and tooling changes made during implementation.

## Policy
- Do not store secrets in this repository.
- Prefer environment variables and ambient cloud roles.
- Record package and system-tool installation changes here whenever they occur.

## Environment Variables
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_MODEL`
- `AZURE_OPENAI_API_VERSION` (optional, default: `2025-04-01-preview`)
- `MARKBRIDGE_WORK_DIR` (optional)

## Current Assumptions
- AWS access is provided by the server's attached IAM role.
- S3 documents may be read directly from URIs such as `s3://...`.
- Azure OpenAI credentials must be provided outside version control.

## Install Changes
- `docling` was confirmed present in the user site environment and is now used as the active PDF route.
- `markitdown` was confirmed present in the user site environment but remains disabled by policy.
- `pdfplumber` was confirmed present in the user site environment but remains disabled by policy.
- Attempted activation of LibreOffice-based `.doc` conversion was blocked because system package installation is not currently available from this session.

## Declared Python Dependencies
- `fastapi`
- `uvicorn`
- `pydantic`
- `python-multipart`
- `boto3`
- `openai`

## Verification Notes
- `python3 -m pytest tests/unit -q` passed with 17 tests
- exporter unit tests added for run-directory file persistence and JSON serialization
- S3 smoke runs succeeded for sample DOCX, PDF, and XLSX objects using the server IAM role
- the active PDF smoke route now uses `docling` with OCR disabled and currently lands on `degraded_accept` for the tested insurance sample
