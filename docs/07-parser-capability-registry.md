# Parser Capability Registry

This registry records parser candidates that fit the current project constraints:
- on-prem deployment preference
- no dependence on paid libraries for MVP
- source-fidelity-oriented Markdown generation
- OCR excluded from active parsing paths

The goal is to keep the candidate set realistic and executable, not merely theoretically possible.

## Classification
- `primary`: current preferred route for the document family
- `secondary`: valid fallback or comparison route
- `experimental`: technically usable but not currently preferred as a standard route
- `policy-review-required`: technically attractive, but licensing or deployment policy needs separate review

## PDF

### Docling
Class:
- `primary`

Strengths:
- layout-aware parsing
- table structure
- formulas
- unified export formats
- suitable for local execution

Weaknesses:
- heavier runtime than simple text extractors
- should be benchmarked for target document families
- installation/runtime footprint is higher than lightweight text tools

### pypdf
Class:
- `secondary`

Strengths:
- lightweight
- simple text extraction
- useful for basic metadata/text paths
- easy on-prem installation path

Weaknesses:
- not the primary choice for complex layout/table understanding
- limited structural fidelity for complex insurance tables

### pdfplumber
Class:
- `secondary`

Strengths:
- useful text, table, and layout-coordinate extraction
- practical for on-prem debugging and comparison

Weaknesses:
- better suited as a structural inspection or comparison tool than as the default end-to-end Markdown path
- may still require significant downstream normalization for complex insurance documents

### pdfminer.six
Class:
- `experimental`

Strengths:
- strong low-level PDF text and layout extraction
- useful for debugging extraction failures

Weaknesses:
- too low-level to serve as the preferred high-fidelity Markdown route on its own
- requires more assembly work than higher-level parser candidates

### Camelot
Class:
- `experimental`

Strengths:
- specialized PDF table extraction
- useful for comparison on table-heavy, text-based PDFs

Weaknesses:
- not an end-to-end document parser
- best treated as a table-specific helper, not the main parsing route

### PyMuPDF / PyMuPDF4LLM
Class:
- `policy-review-required`

Strengths:
- strong PDF extraction capabilities
- attractive direct Markdown-oriented workflows exist

Weaknesses:
- licensing posture requires separate policy and legal review for on-prem commercial usage
- should not enter the default candidate set without that review

## DOCX

### python-docx
Class:
- `primary`

Strengths:
- styles
- paragraph/table structures
- direct OOXML-oriented access
- practical open-source default for on-prem environments

Weaknesses:
- semantic interpretation still requires normalization

### Mammoth
Class:
- `secondary`

Role:
- optional secondary candidate

Strengths:
- style-aware semantic conversion
- useful as an experimental comparison path for simpler DOCX families

Weaknesses:
- not the primary path for maximum structural fidelity
- less suitable as the default route for complex table-heavy insurance documents

## XLSX

### openpyxl
Class:
- `primary`

Strengths:
- merged cells
- formula access
- workbook/sheet-level structure
- practical open-source default for on-prem environments

Weaknesses:
- semantic table understanding must be built separately
- no strong alternative is currently preferred for the same scope

### xlsx2csv
Class:
- `experimental`

Strengths:
- lightweight conversion path for simple spreadsheet extraction
- useful when only flattened row output is needed

Weaknesses:
- weak fit for merged-cell, formula-aware, structure-preserving parsing
- should not be treated as a primary route for CRM spreadsheet fidelity

## DOC

### LibreOffice headless conversion route
Class:
- `primary`

Strengths:
- practical fallback
- keeps main parsing logic unified
- realistic on-prem option for legacy `.doc` handling

Weaknesses:
- conversion quality variance
- adds a conversion step before parsing

### antiword
Class:
- `secondary`

Role:
- optional degraded text fallback only

Strengths:
- lightweight legacy `.doc` text extraction

Weaknesses:
- poor fit for high-fidelity structured Markdown generation
- should not be treated as a primary route for CRM document preservation

### olefile
Class:
- `experimental`

Strengths:
- useful for inspecting legacy OLE document containers and metadata

Weaknesses:
- low-level utility rather than a practical high-fidelity parsing route
- not suitable as a primary `.doc` Markdown path

## Cross-Format Experimental Candidate

### Unstructured
Class:
- `experimental`

Potential Use:
- broad multi-format ingestion and comparison experiments

Weaknesses:
- broader ingestion framework than the current project needs
- current priority is source-fidelity-oriented parsing, not generic document ingestion breadth

### MarkItDown
Class:
- `experimental`

Potential Use:
- multi-format Markdown conversion for quick comparison paths
- experimental baseline generation across several document types

Strengths:
- directly oriented toward Markdown conversion
- broad document-type support in a single tool
- open-source and installable in on-prem Python environments

Weaknesses:
- broad convenience conversion does not automatically mean best structural preservation
- should be benchmarked before entering any default high-fidelity route for insurance CRM documents

## Recommended Current Baseline
- PDF: `Docling` primary, `pypdf` fallback
- DOCX: `python-docx` primary, `Mammoth` optional comparison path
- XLSX: `openpyxl` primary
- DOC: `LibreOffice headless conversion -> python-docx` primary, `antiword` degraded fallback

## Additional Candidate Summary
- PDF secondary: `pdfplumber`
- PDF experimental: `pdfminer.six`, `Camelot`
- PDF policy review required: `PyMuPDF / PyMuPDF4LLM`
- XLSX experimental: `xlsx2csv`
- DOC experimental: `olefile`
- Cross-format experimental: `Unstructured`, `MarkItDown`
