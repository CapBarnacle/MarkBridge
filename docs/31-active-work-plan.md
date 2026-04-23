# 31. Active Work Plan

이 문서는 MarkBridge 작업을 재개할 때 우선 참고하는 현재 기준 작업 목록이다.

기존 계획 문서들은 배경과 상세 맥락을 보존하지만, 작업 우선순위와 "다음에 무엇을 할지"는 이 문서를 기준으로 판단한다.

## 사용 원칙

- 새 작업 플랜을 짤 때는 이 문서를 먼저 본다.
- 오래된 계획 문서와 충돌하면 이 문서를 우선한다.
- 작업을 완료하면 이 문서의 상태를 먼저 갱신한다.
- 세부 설계가 길어지면 별도 문서로 분리하고, 이 문서에는 링크와 현재 상태만 남긴다.

## 현재 기준 문서

| 문서 | 역할 |
|---|---|
| [30-confluence-parsing-guide.md](/home/intak.kim/project/MarkBridge/docs/30-confluence-parsing-guide.md) | 현재 parsing runtime과 decision을 설명하는 컨플루언스용 통합 문서 |
| [27-current-parsing-runtime.md](/home/intak.kim/project/MarkBridge/docs/27-current-parsing-runtime.md) | 코드 기준 runtime 상세 설명 |
| [28-parsing-decision-tree.md](/home/intak.kim/project/MarkBridge/docs/28-parsing-decision-tree.md) | routing, validation, handoff decision tree |
| [09-runtime-parser-status.md](/home/intak.kim/project/MarkBridge/docs/09-runtime-parser-status.md) | runtime parser status snapshot |
| [25-parse-markdown-export-api-confluence.md](/home/intak.kim/project/MarkBridge/docs/25-parse-markdown-export-api-confluence.md) | parse markdown export API와 canonical block API |
| [32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md) | DocumentIR가 chunking/embedding에 충분한지 점검하는 기준 문서 |

## 상태 구분

| 상태 | 의미 |
|---|---|
| `active` | 다음 작업 후보로 계속 유지 |
| `next` | 우선 착수 후보 |
| `blocked` | 외부 의존성이나 결정이 필요 |
| `deferred` | 지금은 하지 않지만 문서상 보존 |
| `done` | 현재 기준으로 완료 |

## 현재 완료로 보는 항목

| 항목 | 상태 | 근거 |
|---|---|---|
| runtime-aware routing 문서화 | `done` | `docs/27`, `docs/28`, `docs/30`에 반영 |
| inspection 실제 동작 문서화 | `done` | 문서 전체 스캔 여부, sampling 없음, LLM prompt 전달값, `complexity_score` 한계 반영 |
| LLM routing recommendation 한계 문서화 | `done` | recommendation은 weak candidate proposal이고 최종 신뢰는 parser output 비교에 둠 |
| baseline/candidate parser 비교 방식 문서화 | `done` | quality signal과 heuristic score 설명 반영 |
| markdown 및 line map 렌더링 문서화 | `done` | preferred markdown, explicit metadata, heuristic matching 설명 반영 |
| validation 수행 주체와 handoff 연결 문서화 | `done` | deterministic validator와 `accept/degraded_accept/hold` 설명 반영 |
| parser registry 표 추가 | `done` | `docs/30`에 포맷별 등록 parser 표 추가 |
| canonical block JSON 설명 추가 | `done` | `docs/30`에 canonical block field와 생성 방식 반영 |

## 현재 진행 전략

현재 우선순위는 "parsing을 더 완벽하게 만든 뒤 다음 단계로 이동"이 아니다.

우선 pipeline을 chunking, embedding, retrieval까지 end-to-end로 연결한 뒤, 실제 downstream 품질을 기준으로 parsing 보강 우선순위를 다시 잡는다.

이 전략을 택하는 이유:

- 현재 parsing은 baseline parser, inspection, routing, validation, Markdown export, line map, canonical block까지 기본 운영 흐름을 갖췄다.
- 각주/미주, HWP 고품질 구조 파싱, table semantic fidelity 같은 보강 항목은 중요하지만, downstream을 붙이기 전에는 우선순위를 정확히 판단하기 어렵다.
- chunking과 retrieval까지 붙여야 어떤 parser metadata가 실제 검색 품질에 도움이 되는지 확인할 수 있다.
- 따라서 지금은 parsing layer를 닫힌 완성물로 만들기보다, downstream feedback loop를 만들 수 있는 최소 end-to-end pipeline을 먼저 완성한다.

현재 전략의 핵심 원칙:

- `DocumentIR` 생성까지를 공통 parsing core로 본다.
- `DocumentIR` 이후에는 두 갈래로 분기한다.
  - 기존 branch: Markdown rendering, line map, canonical block, `/exports/parse-markdown` API
  - 신규 branch: `DocumentIR` 기반 RAG pipeline handoff, chunking, embedding/indexing, retrieval
- Markdown export는 계속 유지한다.
- canonical block은 Markdown 기준 downstream 호환 layer로 유지한다.
- 자체 RAG pipeline의 chunking은 Markdown을 다시 파싱하지 않고 `DocumentIR`을 source of truth로 사용한다.
- Markdown과 canonical block API는 외부 전달, 감사, UI, 기존 연동을 위한 export/API layer로 보존한다.
- chunking 고도화는 parser IR에서 richer context를 받아 별도 handoff payload를 만드는 방향으로 설계한다.
- parsing 보강은 end-to-end 평가 결과를 보고 우선순위화한다.

패키징 전략:

- `parser/export API`는 독립적으로 Docker 패키징 가능한 단위로 유지한다.
- `RAG pipeline`은 별도 module/service/image로 확장할 수 있게 만든다.
- parser/export API 이미지에는 Markdown 생성과 `/exports/parse-markdown` 제공에 필요한 의존성만 넣는다.
- RAG 확장 이미지에는 chunking, embedding, indexing, retrieval 의존성을 별도로 둔다.
- 두 영역의 연결은 내부 Python import보다 artifact/API contract를 우선한다.

개념적 분기 구조:

```text
source
  -> format resolution
  -> inspection
  -> routing
  -> parser execution
  -> DocumentIR
      -> branch A: Markdown rendering/export API
      -> branch B: DocumentIR-based RAG pipeline
```

branch A는 기존 기능으로 유지한다.
branch B는 새로 추가하는 확장 기능이며, branch A의 Markdown API 계약을 깨지 않아야 한다.

## 우선 작업 목록

### 1. DocumentIR Chunking Readiness Audit

상태: `next`

목표:

- 현재 `DocumentIR`가 원본 문맥을 살려 chunking/embedding하기에 충분한지 점검한다.
- parser가 원문에서 알 수 있는 구조 정보와 chunking 단계에서 파생할 정보를 분리한다.
- chunking 전에 보강해야 할 IR 정보를 확정한다.

현재 판단:

- 자체 RAG pipeline의 source of truth는 `DocumentIR`이다.
- `DocumentIR`가 충분히 풍부하지 않으면 chunking 단계가 원본 정보를 재추론하게 된다.
- 따라서 chunker 구현보다 먼저 IR readiness를 확인해야 한다.

해야 할 일:

- 포맷별 대표 샘플의 `DocumentIR` dump 생성
- block kind, heading metadata, table metadata, source span coverage 집계
- required / nice-to-have / derived / export-only 필드 분류
- P1 IR 보강 항목 확정
- readiness 결과를 [32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md)에 반영

참고 문서:

- [32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md)
- [27-current-parsing-runtime.md](/home/intak.kim/project/MarkBridge/docs/27-current-parsing-runtime.md)
- [30-confluence-parsing-guide.md](/home/intak.kim/project/MarkBridge/docs/30-confluence-parsing-guide.md)

### 2. Parser IR 기반 Parsing to Chunking Handoff 설계

상태: `next`

목표:

- chunking이 문맥을 잃지 않도록 parser IR의 구조 정보를 풍부하게 넘기는 handoff payload를 설계한다.
- Markdown-only chunking, canonical block 기반 chunking, parser IR 기반 chunking의 역할을 분리한다.
- pipeline을 끝까지 연결할 수 있는 최소 chunking contract를 먼저 만든다.

현재 판단:

- 현재 API는 canonical Markdown와 canonical block 중심이다.
- chunking 품질을 높이려면 canonical block을 1차 경계로 쓰는 것이 Markdown-only보다 낫다.
- 더 구조적인 chunking을 원하면 `DocumentIR -> ChunkIR` 계층을 별도로 설계하는 편이 안전하다.
- parser IR은 chunking에 필요한 richer context를 가지고 있다.
- 다만 `DocumentIR`을 그대로 외부 계약으로 노출하기보다, chunking용 안정 모델로 변환하는 것이 안전하다.

설계 방향:

1. parser는 지금처럼 `DocumentIR`을 생성한다.
2. branch A는 `DocumentIR`에서 canonical Markdown, markdown line map, canonical block API를 만든다.
3. branch B는 `DocumentIR`에서 RAG 전용 handoff payload를 만든다.
4. 자체 RAG pipeline의 chunking handoff layer는 `DocumentIR`을 주 입력으로 읽는다.
5. line map과 canonical Markdown 정보는 optional back-reference로만 사용한다.
6. handoff layer는 chunker가 쓰기 쉬운 `ChunkInput` 또는 `ChunkSourceBlock` 모델을 만든다.
7. chunker는 이 모델을 기준으로 section-aware chunk를 생성한다.
8. retrieval 평가 결과를 기준으로 parser IR metadata와 chunk policy를 보강한다.

두 branch의 책임:

| branch | 책임 | 유지/확장 기준 |
|---|---|---|
| branch A: Markdown export/API | canonical Markdown 생성, line map 생성, canonical block API 제공 | 기존 외부 연동과 Docker 패키징 대상. 안정성 우선 |
| branch B: RAG pipeline | `DocumentIR` 기반 chunk source 생성, chunking, embedding/indexing, retrieval | 신규 확장 영역. parser API와 dependency 분리 |

source of truth 구분:

| 산출물 | 역할 | chunking에서의 위치 |
|---|---|---|
| `DocumentIR` | parser가 만든 구조적 결과 | 자체 RAG chunking의 primary input |
| canonical Markdown | 외부 전달, 사람이 읽는 결과, 기존 downstream 호환 | chunking primary input 아님 |
| markdown line map | Markdown line과 block/source ref 연결 | citation, audit, UI 연결용 optional reference |
| canonical block JSON | canonical Markdown 기준 export index | 외부 API 호환 layer, 자체 chunking의 보조 참조 |

chunking으로 넘겨야 할 최소 정보:

| 범주 | 필드 후보 | 목적 |
|---|---|---|
| 문서 식별 | `document_id`, `document_name`, `document_format`, `source_uri` | chunk provenance |
| parser 정보 | `selected_parser`, `route_kind`, `parser_version_or_id`, `handoff_decision` | 품질/route 해석 |
| block 식별 | `parser_block_ref`, `block_index`, `block_kind` | chunk source tracking |
| block 내용 | `text`, `content_hash`, optional `rendered_markdown_ref` | chunk 본문 생성과 dedupe |
| 구조 정보 | `heading_level`, `section_path`, `parent_heading_ref`, `chunk_boundary_candidate`, `chunk_boundary_reason`, `chunk_boundary_confidence` | section-aware chunking |
| 위치 정보 | `page_number`, `page_range`, `sheet`, `markdown_line_start`, `markdown_line_end`, `source_span_refs` | citation, UI highlight, audit |
| table 정보 | `table_id`, `table_title`, `header_depth`, `merged_cells`, `row_count`, `column_count`, `table_cells` 또는 `table_markdown` | table-preserving chunking |
| 품질 정보 | `validation_issue_ids`, `quality_flags`, `degraded_route`, `repair_applied`, `unresolved_residue` | chunk trust and filtering |
| 연결 정보 | `canonical_block_id`, `canonical_markdown_name`, `block_download_url` | 기존 export API와 호환 |

중요한 설계 결정:

- chunk text는 기본적으로 IR block에서 직접 생성한다.
- `rendered_markdown`은 필수 content source가 아니라 debug/export reference로 둔다.
- table chunk는 Markdown table 재파싱이 아니라 `TableBlockIR.cells`를 기준으로 만든다.
- canonical Markdown line range는 "이 chunk가 export Markdown 어디와 대응되는가"를 설명하는 보조 정보다.

block kind별 chunking 기본 정책:

| block kind | 기본 정책 |
|---|---|
| `heading` | section boundary로 사용하고, 후속 block의 `section_path`에 포함 |
| `paragraph` | 주변 heading context와 함께 길이 기준으로 병합/분할 |
| `list` | 가능한 한 인접 list끼리 묶고, 상위 heading context 유지 |
| `note` | note/box 의미를 metadata로 유지하고 본문 context와 같이 묶을지 결정 |
| `table` | 가능한 한 table 단위로 유지하되, 큰 table은 header context를 반복하며 row group chunk로 분할 |
| `formula` | 주변 paragraph/table context와 함께 유지 |
| `warning` | 일반 검색 chunk와 분리하거나 quality flag로 표시 |

해야 할 일:

- chunking handoff model 초안 작성
- `DocumentIR -> ChunkInput` 변환 규칙 정의
- `DocumentIR` 이후 branch A/branch B 분기 지점 정의
- branch A의 기존 Markdown export/API contract 보존 테스트 기준 정의
- branch B의 artifact/API contract 초안 정의
- canonical block 기반 chunking과 IR 기반 chunking의 차이 정리
- chunk metadata 최소 필드 확정
- table, heading, list, note, paragraph 처리 정책 정의
- line map과 page/page_range 연결 정책 정의
- validation/handoff/repair 상태를 chunk metadata에 어떻게 반영할지 결정
- 최소 e2e 구현 순서 정의: parse -> chunk -> embed/index placeholder -> retrieval smoke
- parser/export API Docker 패키징과 RAG 확장 패키징의 경계 정의

참고 문서:

- [18-downstream-handoff-contract.md](/home/intak.kim/project/MarkBridge/docs/18-downstream-handoff-contract.md)
- [25-parse-markdown-export-api-confluence.md](/home/intak.kim/project/MarkBridge/docs/25-parse-markdown-export-api-confluence.md)
- [30-confluence-parsing-guide.md](/home/intak.kim/project/MarkBridge/docs/30-confluence-parsing-guide.md)
- [32-document-ir-chunking-readiness.md](/home/intak.kim/project/MarkBridge/docs/32-document-ir-chunking-readiness.md)

### 3. Minimal End-to-End Pipeline 구성

상태: `next`

목표:

- parsing 이후 chunking, embedding/indexing placeholder, retrieval smoke까지 최소 pipeline을 연결한다.
- 이 단계에서는 parsing 완성도를 더 끌어올리기보다, downstream에서 필요한 parsing 보강 항목을 발견하는 데 집중한다.

범위:

- `DocumentIR` 또는 chunking handoff payload에서 chunk 생성
- chunk metadata 저장
- embedding/indexing은 처음에는 stub 또는 local persistence로 시작 가능
- retrieval smoke는 keyword 또는 vector placeholder로 시작 가능
- 실제 RAG answer generation은 아직 범위 밖

해야 할 일:

- chunk model 정의
- chunk artifact 저장 위치와 파일명 정의
- parse run artifact와 chunk artifact 연결
- 최소 chunk list API 또는 artifact contract 정의
- 샘플 문서 2~3개로 retrieval smoke 평가
- 평가 결과를 parsing 보강 backlog에 반영

패키징 경계:

- 1차 구현은 parser/export API package를 깨지 않도록 별도 `src/markbridge_rag` 영역을 우선 검토한다.
- parser core와 shared IR은 `markbridge` package에 유지한다.
- RAG pipeline은 `markbridge` parser core를 소비하되, parser/export API가 RAG dependency를 몰라도 되게 한다.
- embedding/indexing/retrieval dependency는 parser API 기본 dependency에 바로 섞지 않는다.
- 필요하면 `pyproject.toml`에 optional extra를 둔다.
  - 예: `markbridge[parser-api]`, `markbridge[rag]`
- Docker는 장기적으로 두 이미지로 분리할 수 있게 설계한다.
  - `markbridge-parser-api`: parsing, Markdown export, parse-markdown API
  - `markbridge-rag-pipeline`: chunking, embedding, indexing, retrieval

현재 repo 확인 결과:

- 아직 Dockerfile은 없다.
- `pyproject.toml`은 단일 package dependency set만 가진다.
- API 진입점은 `python3 -m markbridge.api`이며 `/exports/parse-markdown` API가 이미 있다.
- `PipelineResult.document`에 `DocumentIR`이 보존되므로 RAG 확장은 parser API와 분리해서 붙일 수 있다.

### 4. Canonical Block API 보강 검토

상태: `active`

목표:

- 현재 canonical block item이 chunking에 충분한지 검토하고 필요한 필드 추가 여부를 결정한다.

현재 상태:

- block item은 metadata 중심이다.
- block item 자체에는 `content`가 없다.
- 실제 block 본문은 `/exports/parse-markdown/{document_id}/blocks/{block_id}/content`에서 line range slice로 제공한다.

검토 후보 필드:

- `content` 또는 `content_preview`
- `page_range`
- `heading_level`
- `source_span_refs`
- `line_refs`
- `table_id`
- `issue_ids`
- `quality_flags`
- `parser_block_ref`

주의:

- block item에 full content를 넣으면 목록 API payload가 커질 수 있다.
- content는 별도 endpoint로 두고, preview나 digest만 목록에 추가하는 방식이 더 안전할 수 있다.

### 5. 각주/미주 처리 한계 문서화 및 지원 여부 결정

상태: `active`

현재 상태:

- 각주/미주 전용 `BlockKind`는 없다.
- DOCX parser는 본문 paragraph/table 중심으로 순회하며 footnotes/endnotes part를 별도로 읽지 않는다.
- PDF나 text route에서는 각주/미주가 일반 텍스트로 우연히 포함될 수는 있지만 구조적으로 보존하지 않는다.

해야 할 일:

- `docs/30`에 현재 각주/미주 처리 한계를 명시
- 각주/미주를 지원 범위에 넣을지 결정
- 지원한다면 DOCX footnotes/endnotes part 추출 방식 조사
- IR 표현을 `note` metadata로 갈지, 별도 `footnote/endnote` kind로 갈지 결정

### 6. DOC Runtime 검증

상태: `active`

현재 상태:

- `.doc` routing scaffold는 있다.
- `libreoffice` route와 `antiword` fallback route가 코드에 등록돼 있다.
- 실제 target runtime에서 설치 여부와 변환 품질 검증이 필요하다.

해야 할 일:

- target runtime에서 `libreoffice` / `soffice` availability 확인
- sample `.doc` parse 실행
- 변환 후 heading/table fidelity 확인
- 실패 시 trace/message/artifact 설명력 확인
- conversion success/failure regression test 추가 여부 검토

참고 문서:

- [26-doc-and-hwp-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/26-doc-and-hwp-execution-plan.md)

### 7. HWP Route 전략 결정

상태: `blocked`

현재 상태:

- intake와 runtime scaffold는 있다.
- `hwp5txt` text route가 등록돼 있지만 현재 runtime availability에 따라 활성화된다.
- 구조 parser 수준의 HWP 지원은 아직 확정되지 않았다.

해야 할 일:

- 실행 가능한 HWP 후보 조사
- conversion-first, dedicated parser, external tool/service 중 선택
- on-prem deployability, licensing, fidelity 비교
- chosen route 또는 explicit defer decision 기록

참고 문서:

- [26-doc-and-hwp-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/26-doc-and-hwp-execution-plan.md)

### 8. UI Highlight / Unresolved Residue 정리

상태: `active`

현재 상태:

- final resolved preview와 source preview는 존재한다.
- 과거 issue line과 아직 unresolved residue line의 시각적 의미가 완전히 분리돼 있지 않다.

해야 할 일:

- `was_flagged_but_resolved`와 `still_unresolved_in_final` 상태 분리
- `<!-- formula-not-decoded -->` 잔존 line badge 추가
- 다중 corruption highlight 지원 검토
- issue 클릭 시 table row/cell 단위 focus 강화 검토

참고 문서:

- [16-processing-and-highlight-flow.md](/home/intak.kim/project/MarkBridge/docs/16-processing-and-highlight-flow.md)
- [21-resolution-first-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/21-resolution-first-execution-plan.md)

### 9. LLM Repair / Patch Anchoring 개선

상태: `active`

현재 상태:

- deterministic repair와 optional LLM repair candidate generation은 있다.
- patch selection fallback은 들어가 있다.
- 일부 케이스에서 `selected_patch_not_applied`가 남을 수 있다.

해야 할 일:

- selected winner의 `target_text` anchoring 개선
- `selected_patch_not_applied` 발생 케이스 수집
- patch 적용 실패 reason을 더 명확히 분류
- final resolved materialization과 resolution accounting의 의미 차이 정리

참고 문서:

- [17-resume-brief.md](/home/intak.kim/project/MarkBridge/docs/17-resume-brief.md)
- [21-resolution-first-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/21-resolution-first-execution-plan.md)

## 오래된 계획 문서 정리 기준

아래 문서는 historical context로 유지한다.
작업 우선순위는 이 문서가 우선한다.

| 문서 | 현재 해석 |
|---|---|
| [10-implementation-backlog.md](/home/intak.kim/project/MarkBridge/docs/10-implementation-backlog.md) | 초기 backlog. 완료된 항목이 섞여 있으므로 세부 history로만 참고 |
| [17-resume-brief.md](/home/intak.kim/project/MarkBridge/docs/17-resume-brief.md) | repair/resolution 중심 resume 기록. 현재 작업 추적은 이 문서로 통합 |
| [21-resolution-first-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/21-resolution-first-execution-plan.md) | resolution-first 설계 맥락. 아직 UI/residue/anchoring 항목은 유효 |
| [22-chunk-boundary-and-format-expansion.md](/home/intak.kim/project/MarkBridge/docs/22-chunk-boundary-and-format-expansion.md) | chunk boundary와 legacy format 초기 계획. 일부 구현 완료/변경됨 |
| [23-chunk-boundary-and-legacy-format-plan.md](/home/intak.kim/project/MarkBridge/docs/23-chunk-boundary-and-legacy-format-plan.md) | 실행 순서 초안. 현재 active plan은 이 문서가 대체 |
| [26-doc-and-hwp-execution-plan.md](/home/intak.kim/project/MarkBridge/docs/26-doc-and-hwp-execution-plan.md) | DOC/HWP 상세 실행 계획. 세부 작업 참고용으로 유지 |

## 다음 세션 시작 체크리스트

1. 이 문서의 `우선 작업 목록`에서 `next` 항목을 확인한다.
2. 관련 기준 문서와 코드 위치를 읽는다.
3. 오래된 계획 문서를 볼 때는 historical context인지 active requirement인지 구분한다.
4. 작업 후에는 이 문서의 상태와 완료 항목을 갱신한다.
