# 32. DocumentIR Chunking Readiness

이 문서는 자체 RAG pipeline을 `DocumentIR` 기준으로 구성하기 전에, 현재 IR이 원본 문맥을 embedding에 충분히 살릴 수 있는지 점검하기 위한 기준 문서다.

실제 BMT 샘플 audit snapshot은 [33-bmt-document-ir-audit.md](/home/intak.kim/project/MarkBridge/docs/33-bmt-document-ir-audit.md)를 참고한다.

핵심 목표는 아래와 같다.

- 원본 구조 보존에 필요한 IR 정보 정의
- 현재 `DocumentIR`에 실제로 담기는 정보 정리
- chunking/embedding 품질을 위해 보강해야 할 IR 정보 식별
- `DocumentIR` 보강 정보와 chunking 단계 파생 정보를 분리
- 이후 `DocumentIR -> ChunkSourceDocument -> Chunk` 설계의 입력 조건 확정

## 1. 설계 원칙

### 1.1 Source of Truth

자체 RAG pipeline의 chunking source of truth는 `DocumentIR`이다.

Markdown은 외부 전달, 감사, UI, 기존 API 호환을 위한 export view로 유지한다.
chunking은 Markdown을 다시 파싱하지 않는다.

```text
DocumentIR
  -> branch A: Markdown rendering/export API
  -> branch B: DocumentIR-based RAG pipeline
```

### 1.2 정보 배치 원칙

| 정보 종류 | 위치 | 이유 |
|---|---|---|
| parser가 원문에서 직접 알 수 있는 구조적 사실 | `DocumentIR` / `BlockIR` / `TableBlockIR` | chunking에서 재추론하면 손실 가능 |
| chunking 정책 적용 중 생기는 파생 정보 | `ChunkSourceDocument` / `Chunk` | parser IR을 chunk policy로 오염시키지 않기 위함 |
| 외부 export와 UI 연결 정보 | Markdown, line map, canonical block sidecar | 기존 API와 audit 보존 |

한 문장 기준:

원천 구조 정보는 IR에 담고, chunking 파생 정보는 chunking 모델에 담는다.

## 2. 현재 IR 구조

현재 코드 기준 IR 정의:

- [src/markbridge/shared/ir.py](/home/intak.kim/project/MarkBridge/src/markbridge/shared/ir.py)

| 타입 | 현재 필드 | 의미 |
|---|---|---|
| `DocumentIR` | `source_format`, `blocks`, `metadata` | 문서 단위 normalized container |
| `BlockIR` | `kind`, `text`, `source`, `metadata` | heading/paragraph/list/note 등 일반 block |
| `TableBlockIR` | `cells`, `table_id`, `title`, `page_range`, `header_depth`, `merged_cells`, `nested_regions`, `continuation_of`, `semantic_type`, `confidence`, `metadata` | table 전용 block |
| `TableCellIR` | `row_index`, `column_index`, `text`, `row_span`, `column_span`, `is_header` | table cell 구조 |
| `SourceSpan` | `page`, `sheet`, `start_line`, `end_line` | 원본 위치 참조 |

현재 `BlockKind`:

| kind | 현재 의미 |
|---|---|
| `heading` | 제목/section boundary 후보 |
| `paragraph` | 일반 본문 |
| `list` | list item 또는 list line |
| `table` | table block |
| `formula` | formula block 후보. 현재 parser route에서 적극 사용되지는 않음 |
| `note` | note/layout box 성격 block |
| `warning` | warning block 후보 |
| `image_ref` | image reference 후보 |
| `footer` | footer 후보 |

## 3. 현재 parser별 IR 정보

| 포맷 / route | 현재 생성 정보 | 현재 강점 | 현재 약점 |
|---|---|---|---|
| PDF / `docling` | `preferred_markdown`, `source=docling.export_to_markdown`, markdown-derived heading/list/table/paragraph, `markdown_line_numbers`, page count 일부 | Markdown heading/table이 살아 있으면 chunk boundary에 유리 | 원본 page/source span이 약함. table 구조는 Markdown table 재구성 수준 |
| PDF / `pypdf` | page별 paragraph block, `metadata.page`, `DocumentIR.metadata.page_count` | page 단위 source hint가 있음 | heading/table 구조 거의 없음. page text가 큰 paragraph로 collapse될 수 있음 |
| PDF / `pdfplumber` | page별 paragraph block, `metadata.page`, `metadata.source=pdfplumber.extract_text` | page hint와 source metadata가 있음 | 현재 policy상 비활성. table 구조는 복원하지 않음 |
| DOCX / `python-docx` | source order paragraph/table 순회, heading heuristic metadata, `TableBlockIR.cells`, `docx_carry_forward`, layout table -> note | block kind와 table cell 구조가 비교적 좋음 | paragraph/table source location 없음. heading source style 원문명 일부만 reason으로 남음. table caption/source span 약함 |
| XLSX / `openpyxl` | sheet heading block, `TableBlockIR.cells`, `metadata.sheet`, `merged_cells`, `DocumentIR.metadata.sheet_count` | sheet boundary와 cell row/column 구조가 좋음 | formula metadata, number format, merged range span, cell address가 없음 |
| DOC / `libreoffice` | DOC -> DOCX 변환 후 DOCX IR 재사용, conversion metadata | 기존 DOCX ruleset 재사용 가능 | 변환 손실 정보와 원본 DOC source span이 약함 |
| DOC / `antiword` | extracted text를 `preferred_markdown`으로 사용, markdown-derived blocks, `extraction_mode=text_fallback` | text fallback이라 최소 내용 확보 가능 | 구조/source/table fidelity 낮음 |
| HWP / `hwp5txt` | extracted text를 `preferred_markdown`으로 사용, markdown-derived blocks, `extraction_mode=text_route` | text route scaffold 존재 | 구조/source/table fidelity 낮음 |

## 4. 원본 보존에 필요한 IR 정보와 현재 상태

### 4.1 문서 수준 정보

| 필요한 정보 | 현재 IR 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| `document_format` | `DocumentIR.source_format` 있음 | 높음 | 유지 | chunk policy 분기 기준 |
| source 이름/URI | `PipelineResult.metadata`에는 있음, `DocumentIR.metadata`에는 일관되지 않음 | 높음 | 보강 필요 | chunk provenance에 필요 |
| selected parser | `PipelineResult.parser_id`에는 있음, `DocumentIR.metadata`에는 일관되지 않음 | 높음 | sidecar 또는 metadata 보강 | route별 신뢰도 해석 |
| route kind | routing status에 있음, IR에는 없음 | 중간 | chunk sidecar에 복사 | degraded/text route filtering |
| validation summary | validation report에 있음, IR에는 없음 | 높음 | chunk sidecar join | chunk quality flag |
| page/sheet count | PDF/XLSX 일부 있음 | 중간 | 유지/정규화 | document-level context |

### 4.2 block 구조 정보

| 필요한 정보 | 현재 IR 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| block kind | `BlockIR.kind` 있음 | 높음 | 유지 | chunk boundary 기본 입력 |
| block text | `BlockIR.text` 있음. table은 cell 중심 | 높음 | 유지 | embedding text 생성 |
| stable parser block ref | `BlockIR.parser_block_ref` 구현됨 | 높음 | 유지 | 외부 API의 `block-{index}` ref와 별도로 chunk/source tracking에 사용 |
| source order | `blocks` tuple 순서로 표현 | 높음 | 유지 | section stack 계산 |
| heading level | heading metadata `level` 일부 있음 | 높음 | 보강/정규화 | PDF/DOCX/XLSX 간 일관성 필요 |
| heading reason/confidence | DOCX/PDF markdown/XLSX sheet heading 일부 있음 | 중간 | 유지/정규화 | inferred heading 신뢰도 |
| source style 정보 | DOCX style reason은 간접적으로만 남음 | 중간 | 보강 후보 | style 기반 heading 신뢰도에 유용 |
| section path | 없음 | 높음 | chunking에서 파생 | heading stack으로 계산 |
| parent heading ref | 없음 | 높음 | chunking에서 파생 | chunk context |

### 4.3 source trace 정보

| 필요한 정보 | 현재 IR 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| page number | PDF route와 single-page markdown-derived route에서 `BlockIR.source.page` 사용 확대 | 높음 | 유지/추가 audit | citation과 retrieval evidence |
| page range | single-page markdown table route에서 우선 채움 | 높음 | 추가 보강 후보 | multi-page chunk 표현 |
| sheet | XLSX에서 `BlockIR.source.sheet`와 table source row range 반영 | 높음 | 유지 | spreadsheet citation |
| source line | Markdown-derived `markdown_line_numbers` 있음 | 중간 | export reference로 유지 | 원본 line은 아님 |
| source span object | `BlockIR.source`가 일부 route에서 실제 사용되기 시작함 | 높음 | 계속 확대 | IR-native traceability |
| canonical markdown line range | line map sidecar에 있음 | 중간 | sidecar 유지 | UI/export 연결 |

### 4.4 table 정보

| 필요한 정보 | 현재 IR 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| table id | DOCX/XLSX/markdown table에서 있음 | 높음 | 유지 | table chunk tracking |
| cells row/col | `TableCellIR`에 있음 | 높음 | 유지 | table-preserving chunking 핵심 |
| header flag | `is_header` 있음. 대부분 first row 기준 | 높음 | 보강 후보 | multi-row header 한계 |
| header depth | markdown/docx/xlsx route에서 기본값 채움 | 높음 | 유지/고도화 | 큰 table split 시 header repeat |
| merged cells 여부 | boolean 일부 있음 | 중간 | 유지/보강 | span 자체는 없음 |
| row/column span | 필드는 있음. 대부분 default 1 | 중간 | 보강 후보 | merged range 복원 시 필요 |
| table title/caption | heading/preceding paragraph 기반 hint 일부 반영 | 중간 | 추가 audit 필요 | retrieval context에 중요 |
| row/column count | 직접 필드는 없음. cells에서 계산 가능 | 중간 | chunking에서 파생 | 파생 가능 |
| cell address / formula / number format | 없음 | 중간 | XLSX 보강 후보 | spreadsheet 품질 향상 |
| surrounding heading | 없음 | 높음 | chunking에서 파생 | section path로 연결 |

### 4.5 품질/검증 정보

| 필요한 정보 | 현재 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| validation issue list | `ValidationReport`에 있음 | 높음 | chunk sidecar에 join | IR 자체보다 sidecar가 적합 |
| issue to block refs | issue location에 일부 있음, line map refs도 있음 | 높음 | join 규칙 필요 | chunk quality flag |
| corruption class | issue details에 있음 | 높음 | chunk metadata에 복사 | formula/table risk |
| handoff decision | `PipelineResult.handoff`에 있음 | 높음 | document/chunk metadata에 복사 | downstream filtering |
| degraded route | route status에 있음 | 중간 | chunk metadata에 복사 | trust level |
| repair applied / unresolved residue | service/evaluation 쪽에 있음 | 중간 | RAG handoff에서 join | answer trust |

### 4.6 특수 구조 정보

| 필요한 정보 | 현재 IR 상태 | chunking 중요도 | 보강 판단 | 비고 |
|---|---|---:|---|---|
| layout table 여부 | DOCX layout table은 `note`와 `source=docx_layout_table`, `box_preserved=True`로 표현 | 중간 | 유지 | note/box chunking에 유용 |
| footnote/endnote | 없음 | 중간 | 결정 필요 | 지원하려면 parser/IR 보강 필요 |
| image reference | `BlockKind.IMAGE_REF`는 있으나 현재 parser에서 적극 사용 안 함 | 낮음 | defer | OCR/image out of current scope |
| footer | `BlockKind.FOOTER`는 있으나 현재 parser에서 적극 사용 안 함 | 낮음 | defer | retrieval noise 가능성 검토 필요 |
| formula block | `BlockKind.FORMULA`는 있으나 현재 corruption/repair 중심 | 중간 | 보강 후보 | formula-aware retrieval 필요 시 |

## 5. 보강 우선순위

### 5.0 April 23, 2026 구현 반영 상태

이번 구현에서 먼저 반영한 항목:

| 항목 | 현재 상태 | 반영 내용 |
|---|---|---|
| stable `parser_block_ref` | 구현됨 | 모든 block에 parser 기준 stable ref를 채움 |
| heading metadata 정규화 | 구현됨 | `heading_level` structured field와 normalized metadata를 함께 채움 |
| `BlockIR.source` 사용 확대 | 부분 구현 | PDF page, XLSX sheet/row range, single-page markdown-derived route에 source span 반영 |
| table `header_depth` | 구현됨 | markdown/docx/xlsx table에 기본 header depth 채움 |
| table title/caption 개선 | 부분 구현 | preceding heading / short caption paragraph 기반 title/caption hint 반영 |

아직 남아 있는 것:

- representative sample dump 기반 coverage audit
- DOCX source span의 더 강한 위치 보존
- validation issue와 block/chunk join 규칙 구체화
- `ChunkSourceDocument` 안정 모델 설계

업데이트:

- BMT 샘플 6건에 대한 첫 audit는 완료했고 결과는 `docs/33`에 정리했다.
- audit 결과상 `parser_block_ref`, `heading_level`, `table_header_depth`, `table_title`은 초기 목표를 충족했다.
- 가장 큰 gap은 PDF/DOCX/DOC의 block-level source span과 table page range다.

### P0. Chunking 전에 먼저 확인해야 하는 것

| 작업 | 이유 | 산출물 |
|---|---|---|
| parser별 실제 `DocumentIR` dump 생성 | 현재 IR 품질을 눈으로 확인해야 함 | sample별 `document_ir.json` |
| IR field coverage 표 자동/수동 작성 | 포맷별 편차 확인 | PDF/DOCX/XLSX/DOC/HWP coverage matrix |
| embedding용 text 생성 가능성 점검 | chunk text를 Markdown 없이 만들 수 있는지 확인 | block kind별 plain/display text 예시 |

### P1. 바로 보강할 가능성이 높은 IR 정보

| 보강 정보 | 대상 | 이유 |
|---|---|---|
| stable `parser_block_ref` | 모든 block | 구현 완료. validation/chunk/source tracking 안정화 |
| `BlockIR.source` 사용 확대 | PDF/DOCX/XLSX | 부분 구현. page/sheet/source span을 IR-native로 보존 |
| heading metadata 정규화 | PDF/DOCX/XLSX | 구현 완료. section hierarchy 계산 안정화 |
| table `header_depth` | DOCX/XLSX/table routes | 구현 완료. 큰 table split 시 header 반복에 필요 |
| table title/caption 개선 | DOCX/XLSX/PDF markdown tables | 부분 구현. table chunk retrieval context 향상 |
| validation issue join 규칙 | sidecar/chunk model | quality-aware retrieval에 필요 |

### P2. 샘플 평가 후 결정할 정보

| 보강 정보 | 판단 기준 |
|---|---|
| `TableCellIR.metadata` 추가 | formula, cell address, number format이 retrieval에 필요하면 추가 |
| footnote/endnote IR 표현 | 실제 문서에서 검색 품질에 영향을 주면 추가 |
| image/footer/formula block 적극 사용 | OCR/image/formula retrieval 범위가 확장될 때 검토 |
| semantic table role | table caption/section context만으로 부족할 때 검토 |

## 6. DocumentIR와 Chunk 모델의 정보 분리

| 정보 | DocumentIR에 있어야 하나 | Chunking에서 만들어도 되나 | 판단 |
|---|---|---|---|
| block kind | 예 | 아니오 | parser 판단 결과 |
| parser block ref | 예 | 아니오 | stable tracking 필요 |
| heading level | 예 | 보조 계산 가능 | parser/source 신호가 중요 |
| heading hierarchy | 아니오 | 예 | heading stack으로 계산 |
| section path | 아니오 | 예 | chunking context 파생 |
| table cells | 예 | 아니오 | 원천 구조 |
| table row group | 아니오 | 예 | chunk split 결과 |
| page/sheet source | 예 | 아니오 | citation 원천 |
| markdown line range | 아니오 | 예/sidecar | export view 연결 |
| validation flags | report 원천 | 예 | chunk metadata로 join |
| chunk id | 아니오 | 예 | chunk output 식별자 |
| token estimate | 아니오 | 예 | chunking policy 산출 |

## 7. 진행 플랜

### Step 1. IR readiness sample audit

목표:

- 현재 parser별 `DocumentIR`가 실제로 어떤 구조와 metadata를 내는지 확인한다.

작업:

1. 대표 샘플을 포맷별로 1~2개 선정
2. parse 실행 후 `PipelineResult.document`를 JSON으로 dump하는 임시 도구 또는 테스트 helper 작성
3. block count, block kind distribution, heading metadata, table metadata, source span coverage를 집계
4. `docs/32`의 coverage 표를 실제 결과로 업데이트

### Step 2. IR 보강 요구사항 확정

목표:

- chunking 전에 반드시 보강할 IR 필드를 확정한다.

작업:

1. required / nice-to-have / derived / export-only로 필드 분류
2. parser별 보강 난이도 추정
3. P1 보강 범위 확정
4. `docs/31-active-work-plan.md`에 구현 순서 반영

### Step 3. IR 보강 구현

우선 후보:

1. stable block ref
2. `BlockIR.source` 사용 확대
3. heading metadata 정규화
4. table header depth/title 보강
5. validation issue join key 정리

### Step 4. ChunkSourceDocument 설계

목표:

- `DocumentIR`를 RAG chunking에 바로 쓰기 좋은 안정 모델로 투영한다.

작업:

1. `ChunkSourceDocument`, `ChunkSourceBlock`, `ChunkSourceTable` 모델 초안
2. `DocumentIR -> ChunkSourceDocument` builder 설계
3. section path 계산 규칙 정의
4. table chunking 입력 표현 정의
5. quality flag join 규칙 정의

### Step 5. 최소 chunking 구현

목표:

- IR 기반으로 Markdown 재파싱 없이 chunk를 만든다.

작업:

1. heading section boundary
2. paragraph/list/note 병합
3. table 보존 또는 row group split
4. chunk artifact 저장
5. retrieval smoke 평가

## 8. 결정해야 할 질문

| 질문 | 후보 | 현재 권장 |
|---|---|---|
| `DocumentIR`에 stable block id를 추가할까 | dataclass field 추가 vs metadata key | field 추가를 검토하되, 초기에는 metadata/key helper도 가능 |
| `TableCellIR`에 metadata/source를 추가할까 | 바로 추가 vs ChunkSourceTableCell에서 보강 | 샘플 audit 후 결정 |
| footnote/endnote를 지원 범위에 넣을까 | defer vs note metadata vs new block kind | 실제 문서 영향 확인 후 결정 |
| chunking에서 Markdown line range를 필수로 둘까 | 필수 vs optional | optional back-reference |
| RAG 확장을 같은 package에 둘까 | `markbridge/chunking` vs `markbridge_rag` | 패키징 분리를 위해 `markbridge_rag` 우선 검토 |

## 9. 한 줄 요약

DocumentIR 기반 chunking을 잘 하려면 먼저 IR이 원본 구조를 충분히 담는지 확인해야 한다.
parser가 원문에서 알 수 있는 구조 정보는 IR에 보존하고, section path나 chunk id 같은 파생 정보는 chunking 모델에서 만든다.
