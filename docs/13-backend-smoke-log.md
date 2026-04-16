# Backend Smoke Log

This document records backend smoke-run results against real sample documents when available.

## S3 Smoke Runs

Bucket:
- `s3://rag-580075786326-ap-northeast-2/`

Verified samples:

| Sample | Format | Route | Handoff | Notes |
|---|---|---|---|---|
| `300233_계약관계자변경.docx` | DOCX | `python-docx` | `accept` | trace events: 26, markdown generated |
| `산출방법서_신한큐브종합건강상해보험(무배당, 해약환급금 미지급형)_230404_v2.pdf` | PDF | `docling` | `degraded_accept` | OCR disabled, trace events: 26, markdown generated, warning-level table structure issue remains |
| `건강보험진료통계-다빈도상병별현황_2022.xlsx` | XLSX | `openpyxl` | `accept` | trace events: 26, markdown generated, openpyxl emitted a workbook-style warning |
| `(무)종신보험표준형_20210101_산출방법서.doc` | DOC | `unsupported` | `hold` | no enabled conversion route yet |

## Current Interpretation
- DOCX, PDF, and XLSX complete end-to-end from S3 input through export and handoff decision.
- Legacy `.doc` remains blocked until LibreOffice conversion becomes available.
- Current PDF route is functional through `docling` and preserves more original Markdown structure than the previous `pypdf` path.
- The tested insurance PDF still produces warning-level table structure anomalies after markdown-to-IR normalization, so current handoff is `degraded_accept` rather than `accept`.
