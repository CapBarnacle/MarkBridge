# Google AI Studio UI Prompt

Use the following prompt as a starting point when generating the parsing UI code.

```text
Build a modern parsing trace UI for a Python-based document parsing backend called MarkBridge.

Context:
- MarkBridge is the parsing layer for a life-insurance CRM AI Assistant RAG pipeline.
- The backend parses PDF, DOCX, XLSX, and DOC documents into source-faithful Markdown.
- The system also produces trace events, validation issues, and a downstream handoff decision.
- OCR is out of scope.
- The UI should support document upload, parse execution, trace visualization, validation issue review, and Markdown result preview.
- The UI should be designed so it can later be reused as a common parsing/inspection interface.

Required screens/components:
1. Upload panel for one document at a time
2. Parse execution status panel
3. Step-by-step trace timeline
4. Validation issues list with severity, location hint, and human-readable excerpt
5. Markdown preview panel
6. Artifact summary panel:
   - selected parser
   - document type
   - handoff decision
   - warnings/issues count

Design direction:
- modern, clean, production-like
- use shadcn-style component patterns
- Tailwind CSS-friendly structure
- avoid purple-heavy default styling
- focus on readability for trace and issue inspection
- desktop-first but responsive
- make the trace timeline and issue review especially strong

Data assumptions:
- Trace stages include:
  ingest, inspection, routing, parsing, normalization, validation, repair, rendering, export
- Validation severities:
  info, warning, error
- Handoff decisions:
  accept, degraded_accept, hold

Output:
- Produce frontend code structure that can later be connected to a Python API
- Use mock JSON data for now
- Keep components modular and reusable
```
