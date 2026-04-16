# Runtime Parser Status

This document separates parser capability from runtime reality.

Capability answers:
- what the project considers a supported candidate

Runtime status answers:
- what is currently installed
- what is currently enabled
- what may actually be selected by routing

## Status Fields
- `installed`: whether the dependency is present in the current environment
- `enabled`: whether project policy currently allows routing to use it
- `reason`: why a parser is unavailable or disabled

## Current Environment Snapshot

| Parser | Document Type | Installed | Enabled | Intended Role | Reason / Notes |
|---|---|---:|---:|---|---|
| Docling | PDF | true | true | primary | active preferred PDF route, configured with OCR disabled |
| pypdf | PDF | true | true | fallback | deterministic fallback PDF route |
| pdfplumber | PDF | true | false | secondary | installed but not enabled in the active route set |
| pdfminer.six | PDF | false | false | experimental | not installed in current environment |
| Camelot | PDF | false | false | experimental | not installed in current environment |
| PyMuPDF / PyMuPDF4LLM | PDF | true / false | false | policy review required | `fitz` is installed but `pymupdf4llm` is not, and policy review is still required |
| python-docx | DOCX | true | true | primary | enabled default DOCX parser |
| Mammoth | DOCX | false | false | optional | not installed in current environment |
| openpyxl | XLSX | true | true | primary | enabled default XLSX structural parser |
| xlsx2csv | XLSX | false | false | experimental | not installed in current environment |
| LibreOffice headless | DOC | false | false | primary | `libreoffice` / `soffice` command not present |
| antiword | DOC | false | false | degraded fallback | command not present |
| olefile | DOC | true | false | experimental | installed but not enabled as an active parsing route |
| Unstructured | multi-format | false | false | experimental | not installed in current environment |
| MarkItDown | multi-format | true | false | experimental | installed but not enabled in the active route set |

## Effective Current Route Set
- PDF: `docling`, with `pypdf` kept available as a deterministic fallback
- DOCX: `python-docx`
- XLSX: `openpyxl`
- DOC: no enabled primary route at the moment
- HWP: no enabled route

This means the current environment can support deterministic parsing for:
- DOCX
- XLSX
- high-fidelity PDF paths via `docling`
- simple fallback PDF paths via `pypdf`

It does not yet support the intended `.doc` conversion route or any active HWP route.

## Current Policy
- Routing should consider only parsers with `installed = true` and `enabled = true`.
- Parsers may remain listed in the capability registry even when they are not currently installed.
- Unavailable parsers should still be visible in trace or diagnostics when they were excluded from consideration.

## Why This Exists
- to prevent routing from recommending non-executable tools
- to explain why a parser was not selected
- to keep on-prem deployment choices explicit
- to support future environment-specific configuration

## Detection Basis
Current status was derived from:
- Python import availability for package-based parsers
- shell command discovery for system tools such as `libreoffice`, `soffice`, and `antiword`
