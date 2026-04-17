# UI API Contract

이 문서는 외부에서 생성한 UI를 MarkBridge 백엔드에 연결할 때 필요한 최소 계약을 정리한다.

중요:

- 이 문서는 UI 연동 최소 계약을 설명한다.
- downstream canonicalization 정책은 더 이상 고정 `source` 가 아니다.
- 현재 source/resolved 선택 로직의 최종 truth 는 `src/markbridge/api/service.py`, `docs/17-resume-brief.md`, `docs/21-resolution-first-execution-plan.md` 에 맞춘다.

## Active Endpoints
- `GET /health`
- `GET /v1/runtime-status`
- `GET /v1/s3/objects`
- `POST /v1/parse/upload`
- `POST /v1/parse/s3`

## 1. Runtime Status
### Request
```http
GET /v1/runtime-status
```

### Response
```json
{
  "parsers": [
    {
      "parser_id": "docling",
      "installed": true,
      "enabled": true,
      "reason": null,
      "supported_formats": ["pdf"],
      "route_kind": "primary"
    }
  ]
}
```

### Response Notes
- `supported_formats`: 이 parser/tool 이 현재 runtime에서 담당하는 문서 포맷 목록
- `route_kind`: `primary`, `fallback`, `secondary`, `degraded_fallback`, `text_route`, `experimental` 중 하나
- `degraded_fallback` 는 품질 저하를 감수하는 legacy fallback 을 의미한다. 현재 `antiword` 가 여기에 해당한다.
- `text_route` 는 구조 fidelity 가 아니라 text extraction 중심의 경로를 의미한다. 현재 `hwp5txt` 가 여기에 해당한다.

## 2. S3 Object List
S3 콤보박스와 검색형 선택 UI는 이 API를 기준으로 연결한다.

### Request
```http
GET /v1/s3/objects?bucket=example-bucket&prefix=insurance/&limit=100
```

### Query Parameters
- `bucket`: required
- `prefix`: optional
- `limit`: optional, default `100`, max `500`

### Response
```json
{
  "objects": [
    {
      "label": "sample-policy.pdf",
      "bucket": "example-bucket",
      "key": "insurance/sample-policy.pdf",
      "s3_uri": "s3://example-bucket/insurance/sample-policy.pdf",
      "document_format": "pdf",
      "size_bytes": 248133,
      "updated_at": "2026-04-03T08:20:00Z"
    }
  ]
}
```

### UI Notes
- `label` 은 콤보박스 기본 표시값으로 사용한다.
- `s3_uri` 는 선택 완료 후 parse 요청에 바로 전달할 수 있다.
- `document_format` 은 파일 타입 뱃지나 필터링에 사용한다.
- `updated_at`, `size_bytes` 는 보조 메타 정보로 사용한다.
- 현재는 지원 확장자만 반환한다: `pdf`, `docx`, `xlsx`, `doc`, `hwp`

## 3. Parse Upload
### Request
```http
POST /v1/parse/upload
Content-Type: multipart/form-data
```

### Form Fields
- `file`: required
- `llm_requested`: optional boolean
- `parser_hint`: optional string

## 4. Parse S3
### Request
```http
POST /v1/parse/s3
Content-Type: application/json
```

### Body
```json
{
  "s3_uri": "s3://example-bucket/insurance/sample-policy.pdf",
  "llm_requested": false,
  "parser_hint": "docling"
}
```

## 5. Parse Response Shape
두 parse endpoint 는 동일한 응답 모델을 사용한다.

### Top-Level Fields
- `request_id`
- `source`
- `routing`
- `handoff`
- `trace`
- `issues`
- `artifacts`
- `markdown`
- `markdown_line_map`
- `repair_candidates`
- `suggested_resolved_markdown`
- `suggested_resolved_patches`
- `final_resolved_markdown`
- `final_resolved_patches`
- `resolution_summary`
- `downstream_handoff`
- `evaluation`
- `llm_diagnostics`
- `llm_requested`
- `llm_used`
- `notes`

### UI-Critical Fields
- `routing.primary_parser`
- `source.document_format`
- `handoff.decision`
- `issues`
- `trace.events`
- `markdown`
- `markdown_line_map`
- `repair_candidates`
- `suggested_resolved_markdown`
- `suggested_resolved_patches`
- `final_resolved_markdown`
- `final_resolved_patches`
- `resolution_summary`
- `downstream_handoff`
- `evaluation`
- `llm_diagnostics`

### Repair Candidate Shape
`repair_candidates` 는 현재 자동 적용 결과가 아니라 reviewable candidate 다.

```json
{
  "issue_id": "issue-123",
  "repair_type": "formula_reconstruction",
  "strategy": "deterministic_transliteration_with_llm_review",
  "origin": "deterministic",
  "source_text": "1.3. 해지율(      )에 관한 사항",
  "source_span": "",
  "candidate_text": "1.3. 해지율( q x + t l )에 관한 사항",
  "normalized_math": "q_{x+t} l",
  "confidence": 0.5,
  "rationale": "Formula-like corruption requires review.",
  "requires_review": true,
  "llm_recommended": true,
  "block_ref": "block-13",
  "markdown_line_number": 41,
  "location_hint": "block 13",
  "severity": "warning",
  "patch_proposal": {
    "action": "replace_text",
    "target_text": "1.3. 해지율(      )에 관한 사항",
    "replacement_text": "1.3. 해지율( q x + t l )에 관한 사항",
    "block_ref": "block-13",
    "location_hint": "block 13",
    "markdown_line_number": 41,
    "confidence": 0.5,
    "rationale": "Formula-like corruption requires review.",
    "uncertain": true
  }
}
```

### Repair Candidate Semantics
- `origin` 은 `deterministic` 또는 `llm` 이다.
- `patch_proposal` 은 원문 markdown를 즉시 변경하지 않는 reviewable patch다.
- downstream 단계는 원본 `markdown` 과 `repair_candidates[*].patch_proposal` 을 함께 전달받아 `resolved_markdown` 생성 여부를 결정한다.
- 현재 제품 기본값은 auto-apply 가 아니라 review-first 다.
- run artifact가 있으면 `export_dir` 아래에 아래 파일이 추가로 저장된다.
  - `repair_candidates.json`
  - `llm_formula_repair.json`
  - `suggested_resolved.md`
  - `suggested_resolved_patches.json`

### Suggested Resolved Markdown
- `suggested_resolved_markdown` 은 원문 markdown를 직접 바꾼 canonical output 이 아니다.
- review를 돕기 위한 preview copy 다.
- issue별로 가장 강한 patch proposal 하나를 선택해 line-aware replacement 를 적용한 결과다.
- 현재 구현은 같은 issue 안에서 `llm` candidate를 `deterministic` candidate보다 우선한다.

### Final Resolved Markdown
- `final_resolved_markdown` 은 현재 backend가 조합한 최종 resolved candidate 다.
- 실제 downstream canonical 본문은 `downstream_handoff.preferred_markdown_kind` 로 결정한다.
- placeholder residue가 남으면 `final_resolved_markdown` 이 존재해도 canonical downstream은 `source` 로 되돌아갈 수 있다.
- 따라서 UI는 `final_resolved_markdown exists` 와 `downstream actually receives resolved` 를 같은 의미로 취급하면 안 된다.

### Downstream Handoff
```json
{
  "policy": "resolved_with_fallback",
  "preferred_markdown_kind": "resolved",
  "review_required": true,
  "source_markdown_available": true,
  "suggested_resolved_available": true,
  "final_resolved_available": true,
  "rationale": [
    "A resolved markdown artifact was assembled from the highest-ranked repair patches.",
    "Downstream should prefer the resolved markdown while preserving the source markdown for audit and fallback."
  ]
}
```

- 현재 handoff 는 조건부다.
- 대표 상태:
  - `source_only`
  - `dual_track_review`
  - `resolved_preferred`
  - `resolved_with_fallback`
- recovery가 충분히 성공하면 `preferred_markdown_kind=resolved` 가 가능하다.
- `<!-- formula-not-decoded -->` placeholder residue가 `final_resolved_markdown` 에 남아 있으면 canonical downstream은 다시 `source` 여야 한다.
- UI는 `preferred_markdown_kind`, `review_required`, `final_resolved_available` 을 함께 보여야 한다.

### Parse Evaluation
```json
{
  "readiness_score": 74,
  "readiness_label": "reviewable",
  "issue_count": 1,
  "repair_candidate_count": 2,
  "deterministic_candidate_count": 1,
  "llm_candidate_count": 1,
  "suggested_patch_count": 1,
  "review_required": true,
  "recommended_next_step": "Use source markdown for downstream and inspect suggested repairs before canonicalization.",
  "rationale": [
    "Detected issues: 1",
    "Repair candidates: 2",
    "LLM reconstructions generated: 1",
    "Suggested resolved patches applied: 1"
  ]
}
```

- `evaluation` 은 parse 품질과 복원 진행 상태를 빠르게 요약하기 위한 UI/ops 보조 정보다.
- 현재 점수는 heuristic 이며 canonical quality gate 를 대체하지 않는다.

## 6. Recommended UI Mapping
- Sidebar status badge: `/health`, `/v1/runtime-status`
- S3 combobox: `/v1/s3/objects`
- Source picker actions:
  - local mode -> `POST /v1/parse/upload`
  - S3 mode -> `POST /v1/parse/s3`
- Artifact summary:
  - `routing.primary_parser`
  - `source.document_format`
  - `handoff.decision`
  - `issues.length`
  - `trace.warnings.length`
- Trace timeline:
  - `trace.events[*].stage`
  - `trace.events[*].status`
  - `trace.events[*].component`
  - `trace.events[*].message`
  - `trace.events[*].timestamp`
  - `trace.events[*].data`
- Issue panel:
  - `issues[*].severity`
  - `issues[*].code`
  - `issues[*].message`
  - `issues[*].block_ref`
  - `issues[*].excerpts`
- Markdown preview:
  - `markdown`
  - `markdown_line_map`
- Repair review panel or side drawer:
  - `repair_candidates[*].source_text`
  - `repair_candidates[*].candidate_text`
  - `repair_candidates[*].normalized_math`
  - `repair_candidates[*].confidence`
  - `repair_candidates[*].rationale`
  - `repair_candidates[*].origin`
  - `repair_candidates[*].markdown_line_number`
  - `repair_candidates[*].patch_proposal`
- Markdown preview toggle:
  - `markdown`
  - `suggested_resolved_markdown`
  - `suggested_resolved_patches`
- Downstream handoff card:
  - `downstream_handoff.policy`
  - `downstream_handoff.preferred_markdown_kind`
  - `downstream_handoff.review_required`
  - `downstream_handoff.rationale`
- Evaluation card:
  - `evaluation.readiness_score`
  - `evaluation.readiness_label`
  - `evaluation.recommended_next_step`
  - `evaluation.rationale`
