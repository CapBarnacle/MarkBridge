# API List

- CRM RAG Method에서는 최종 API 단위로 parser 결과를 받아 chunking 시스템이 재사용한다.
- 본 문서는 MarkBridge parser export API를 Confluence 공유용 형식으로 정리한 초안이다.

| 구분 | Method | API 경로 | 목적 | 비고 |
| --- | --- | --- | --- | --- |
| 문서 목록 API | `GET` | `/exports/parse-markdown` | parser 완료 Markdown 문서 목록 조회 | chunking 시스템이 증분 수집 시작점으로 사용 |
| 문서 내용 API | `GET` | `/exports/parse-markdown/{document_id}/content` | 문서별 canonical markdown 본문 다운로드 | 외부 시스템은 최종 markdown 파일만 수신 |
| block 목록 API | `GET` | `/exports/parse-markdown/{document_id}/blocks` | 문서별 canonical block 목록 및 메타데이터 조회 | 구조 기반 chunking이 필요할 때 사용 |
| block 내용 API | `GET` | `/exports/parse-markdown/{document_id}/blocks/{block_id}/content` | 개별 canonical block markdown 다운로드 | 부분 재색인 및 block 단위 처리 용도 |

---

## 1. parse-markdown

`GET /exports/parse-markdown`

### 목적

parser 완료된 markdown 문서 목록을 외부 chunking 시스템이 증분 수집할 수 있도록 제공한다.

### 설계의도

- parser 결과를 파일시스템 직접 접근 없이 API로 노출한다.
- 문서 상태와 마지막 완료 시각을 함께 제공해 chunking 시스템이 증분 조회할 수 있게 한다.
- 문서별 본문 다운로드 URL을 같이 내려서 후속 API 호출을 단순화한다.

### Request

| 필드 | 타입 | 필수 Y/N | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `updated_after` | `string(datetime)` | N | `2026-04-15T00:00:00Z` | 해당 시각 이후 완료/갱신된 문서만 조회 |
| `limit` | `integer` | N | `100` | 최대 조회 건수 |
| `cursor` | `string` | N | `eyJvZmZzZXQiOjEwMH0=` | 다음 페이지 조회용 커서 |
| `parse_status` | `string` | N | `completed` | 특정 parse 상태만 필터링 |

### Response

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `items` | `array` | 조회된 parse markdown 문서 목록 |
| `items[].document_id` | `string` | 문서 식별자 |
| `items[].document_name` | `string` | 원본 문서 파일명 |
| `items[].canonical_markdown_name` | `string` | parser 최종 markdown 파일명 |
| `items[].parse_status` | `string` | parse 상태. `completed`, `running`, `pending`, `failed` |
| `items[].last_parse_completed_at` | `string(datetime)` | 마지막 parse 완료 시각 |
| `items[].markdown_download_url` | `string` | markdown 다운로드 API 경로 |
| `next_cursor` | `string \| null` | 다음 페이지 조회 시각 |

### Response 예시

```json
{
  "items": [
    {
      "document_id": "doc_af621b8736a2",
      "document_name": "300233_계약관계자변경.docx",
      "canonical_markdown_name": "300233_계약관계자변경.docx-1.md",
      "parse_status": "completed",
      "last_parse_completed_at": "2026-04-15T02:53:39Z",
      "markdown_download_url": "/exports/parse-markdown/doc_af621b8736a2/content"
    },
    {
      "document_id": "doc_b19c24d88fe1",
      "document_name": "300138_라이프앱가능업무.docx",
      "canonical_markdown_name": "300138_라이프앱가능업무.docx-1.md",
      "parse_status": "running",
      "last_parse_completed_at": "2026-04-15T02:10:11Z",
      "markdown_download_url": "/exports/parse-markdown/doc_b19c24d88fe1/content"
    }
  ],
  "next_cursor": "2026-04-15T02:53:39Z"
}
```

### 상태로직

| 내부구분 | 설명 |
| --- | --- |
| 문서 목록 조회 | 문서별 최신 parse 결과를 조회한다. |
| Parse 완료 문서 필터링 | `parse_status`, `last_parse_completed_at` 기준으로 조회 대상을 필터링한다. |
| 증분 조회 적용 | `updated_after`, `cursor`, `limit` 조건을 반영한다. |
| 공통 응답 변환 | 외부 시스템 공통 contract 에 맞게 최소 필드만 매핑한다. |
| 다운로드 URL 구성 | 각 문서별 markdown 다운로드 URL 을 응답에 포함한다. |
| `parse_status = completed` | chunking 대상이다. |
| `parse_status = running/pending/failed` | 다운로드 불가 또는 재시도 필요 상태다. |

---

## 2. parse-markdown content

`GET /exports/parse-markdown/{document_id}/content`

### 목적

특정 문서의 최종 canonical markdown 본문을 다운로드한다.

### 설계의도

- 외부 시스템은 source markdown, resolved markdown 내부 구분을 알 필요가 없다.
- parser 서버가 최종 선택한 canonical markdown 1개만 제공한다.
- chunking 시스템은 이 API만으로 바로 본문 수집이 가능하다.

### Path Parameter

| 필드 | 타입 | 필수 Y/N | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `document_id` | `string` | Y | `doc_af621b8736a2` | 문서 식별자 |

### Response

| 항목 | 타입 | 설명 |
| --- | --- | --- |
| Body | `text/markdown` | canonical markdown 본문 |
| Header `Content-Type` | `string` | `text/markdown; charset=utf-8` |
| Header `Content-Disposition` | `string` | 다운로드 파일명 지정 |
| Header `ETag` | `string` | markdown artifact 버전 식별자 |
| Header `Last-Modified` | `string(datetime)` | 마지막 parse 완료 시각 |

### Response 예시

실제 구현 시에는 아래 JSON wrapper 대신 `text/markdown` raw body 반환을 권장한다.

```json
{
  "document_id": "doc_af621b8736a2",
  "document_name": "300233_계약관계자변경.docx",
  "canonical_markdown_name": "300233_계약관계자변경.docx-1.md",
  "content_type": "text/markdown; charset=utf-8",
  "content": "## 1) 계약자변경 유의사항 및 공통사항\n> 계약자 변경 시 유의사항\n\n## 3) 계약자 변경 구비서류\n| 접수방법 |  | 구비서류 안내 |"
}
```

실제 raw body 예시는 아래와 같다.

```md
## 1) 계약자변경 유의사항 및 공통사항
> 계약자 변경 시 유의사항
> 본인 확인이 필요한 경우 추가 서류를 제출해야 합니다.

## 3) 계약자 변경 구비서류
| 접수방법 |  | 구비서류 안내 |
| --- | --- | --- |
| 우편/ FC방문 접수 |  | ... |
```

### 상태로직

| 내부구분 | 설명 |
| --- | --- |
| 문서 조회 | `document_id`로 문서를 조회한다. |
| Parse artifact 확인 | markdown artifact 존재 여부를 확인한다. |
| 권한/상태 검증 | 다운로드 가능한 parse 상태인지 검증한다. |
| markdown 원문 로드 | 저장된 canonical markdown 내용을 읽는다. |
| 파일 응답 반환 | `text/markdown` 형식으로 응답한다. |

---

## 3. parse-markdown blocks

`GET /exports/parse-markdown/{document_id}/blocks`

### 목적

특정 문서의 canonical block 목록과 block 메타데이터를 조회한다.

### 설계의도

- 전체 markdown만 받는 방식 외에 parser가 정리한 구조 단위 그대로 가져갈 수 있게 한다.
- heading, paragraph, table, note 단위 경계를 chunking 시스템이 직접 사용할 수 있게 한다.
- 부분 재처리나 block 단위 재색인에 필요한 식별자와 line range를 함께 제공한다.

### Path Parameter

| 필드 | 타입 | 필수 Y/N | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `document_id` | `string` | Y | `doc_af621b8736a2` | 문서 식별자 |

### Response

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `document_id` | `string` | 문서 식별자 |
| `document_name` | `string` | 원본 문서 파일명 |
| `canonical_markdown_name` | `string` | parser 최종 markdown 파일명 |
| `parse_status` | `string` | parse 상태 |
| `last_parse_completed_at` | `string(datetime)` | 마지막 parse 완료 시각 |
| `blocks` | `array` | canonical block 목록 |
| `blocks[].block_id` | `string` | block 식별자 |
| `blocks[].block_index` | `integer` | 문서 내 순서 |
| `blocks[].block_kind` | `string` | `heading`, `paragraph`, `list`, `table`, `note`, `warning` 등 |
| `blocks[].markdown_line_start` | `integer` | block 시작 줄 |
| `blocks[].markdown_line_end` | `integer` | block 끝 줄 |
| `blocks[].page_number` | `integer \| null` | 원본 페이지 번호 |
| `blocks[].block_download_url` | `string` | block 다운로드 API 경로 |
| `blocks[].chunk_boundary_candidate` | `boolean` | parser가 chunk boundary 후보로 판단했는지 여부 |

### Response 예시

```json
{
  "document_id": "doc_af621b8736a2",
  "document_name": "300233_계약관계자변경.docx",
  "canonical_markdown_name": "300233_계약관계자변경.docx-1.md",
  "parse_status": "completed",
  "last_parse_completed_at": "2026-04-15T02:53:39Z",
  "blocks": [
    {
      "block_id": "block-0001",
      "block_index": 1,
      "block_kind": "heading",
      "markdown_line_start": 1,
      "markdown_line_end": 1,
      "page_number": 1,
      "block_download_url": "/exports/parse-markdown/doc_af621b8736a2/blocks/block-0001/content",
      "chunk_boundary_candidate": true
    },
    {
      "block_id": "block-0002",
      "block_index": 2,
      "block_kind": "note",
      "markdown_line_start": 2,
      "markdown_line_end": 6,
      "page_number": 1,
      "block_download_url": "/exports/parse-markdown/doc_af621b8736a2/blocks/block-0002/content",
      "chunk_boundary_candidate": false
    },
    {
      "block_id": "block-0003",
      "block_index": 3,
      "block_kind": "table",
      "markdown_line_start": 8,
      "markdown_line_end": 14,
      "page_number": 1,
      "block_download_url": "/exports/parse-markdown/doc_af621b8736a2/blocks/block-0003/content",
      "chunk_boundary_candidate": false
    }
  ]
}
```

### 상태로직

| 내부구분 | 설명 |
| --- | --- |
| block 목록 조회 | parser가 최종 canonical markdown 구성에 사용한 block 구조를 반환한다. |
| `block_index` | 문서 내 canonical 순서를 의미한다. |
| `chunk_boundary_candidate` | heading 등 chunk 분리 후보를 바로 식별할 수 있게 한다. |
| `page_number` | 원문 anchor가 남아 있으면 source 추적에 사용한다. |

---

## 4. parse-markdown block content

`GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content`

### 목적

개별 canonical block markdown 본문을 다운로드한다.

### 설계의도

- 전체 문서 재다운로드 없이 필요한 block만 내려받을 수 있게 한다.
- block 단위 chunking, 부분 재색인, 특정 block 재검증에 사용한다.

### Path Parameter

| 필드 | 타입 | 필수 Y/N | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `document_id` | `string` | Y | `doc_af621b8736a2` | 문서 식별자 |
| `block_id` | `string` | Y | `block-0003` | block 식별자 |

### Response

| 항목 | 타입 | 설명 |
| --- | --- | --- |
| Body | `text/markdown` | 개별 canonical block markdown 본문 |
| Header `Content-Type` | `string` | `text/markdown; charset=utf-8` |
| Header `Last-Modified` | `string(datetime)` | 마지막 parse 완료 시각 |

### Response 예시

```md
| 접수방법 |  | 구비서류 안내 |
| --- | --- | --- |
| 우편/ FC방문 접수 |  | ... |
```

또는

```md
> 계약자 변경 시 유의사항
> 본인 확인이 필요한 경우 추가 서류를 제출해야 합니다.
```

### 상태로직

| 내부구분 | 설명 |
| --- | --- |
| block 다운로드 | block 목록 API에서 조회한 `block_id` 기준으로 block 본문을 조회한다. |
| 부분 재색인 | 특정 block만 다시 수집하거나 갱신할 때 사용할 수 있다. |
| block 종류 유지 | heading, note, table 등 markdown 표현을 그대로 내려준다. |

---

## 5. Chunking 시스템 사용 예시

### 5.1 단순 수집 방식

1. `GET /exports/parse-markdown` 호출
2. `parse_status = completed` 문서만 필터링
3. `markdown_download_url` 기준으로 전체 markdown 다운로드
4. 자체 규칙으로 chunk 생성

### 5.2 구조 기반 수집 방식

1. `GET /exports/parse-markdown` 호출
2. `parse_status = completed` 문서만 필터링
3. `GET /exports/parse-markdown/{document_id}/blocks` 호출
4. `block_kind`, `chunk_boundary_candidate`, line range 기준으로 chunk 계획 수립
5. 필요 시 `GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content` 호출
6. block 단위 또는 block 묶음 단위로 chunk 생성

### 5.3 curl 예시

```bash
curl "http://parser-a:8000/exports/parse-markdown?updated_after=2026-04-15T00:00:00Z&limit=100&parse_status=completed"
```

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/content" \
  -o "300233_계약관계자변경.docx-1.md"
```

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/blocks"
```

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/blocks/block-0003/content" \
  -o "doc_af621b8736a2-block-0003.md"
```

### 5.4 Python 예시

```python
import requests

base_url = "http://parser-a:8000"
cursor = "2026-04-15T00:00:00Z"

response = requests.get(
    f"{base_url}/exports/parse-markdown",
    params={
        "updated_after": cursor,
        "limit": 100,
        "parse_status": "completed",
    },
    timeout=30,
)
response.raise_for_status()
payload = response.json()

for document in payload["items"]:
    if document["parse_status"] != "completed":
        continue

    blocks_response = requests.get(
        f"{base_url}/exports/parse-markdown/{document['document_id']}/blocks",
        timeout=30,
    )
    blocks_response.raise_for_status()
    blocks_payload = blocks_response.json()

    for block in blocks_payload["blocks"]:
        block_md = requests.get(
            f"{base_url}{block['block_download_url']}",
            timeout=30,
        ).text
        save_block(document, block, block_md)
```

---

## 6. 구현 포인트

| 항목 | 설명 |
| --- | --- |
| 증분 조회 기준 | `last_parse_completed_at` 기반 cursor 관리 |
| 최소 dedupe key | `document_id + last_parse_completed_at` |
| block 단위 dedupe | `document_id + block_id + last_parse_completed_at` 권장 |
| 내부 구조 은닉 | 외부에는 `run_id` 대신 `document_id`만 노출 |
| canonical 선택 | parser 서버가 내부적으로 결정하고 외부에는 최종 결과만 제공 |

---

## 7. API 개발 준비

| 준비 항목 | 설명 |
| --- | --- |
| `document_id` 매핑 규칙 | 기존 `run_id`와 분리된 외부 문서 식별자 관리 필요. 예: `doc_` + 12자리 hex |
| export index 저장소 | `.markbridge/runs` 아래 run artifact를 문서 기준으로 역인덱싱할 수 있어야 함 |
| 목록 조회 서비스 | `updated_after`, `cursor`, `limit`, `parse_status` 조건으로 export 목록 조회 필요 |
| canonical markdown 조회 서비스 | run artifact에서 최종 markdown 경로와 파일명을 찾아 raw body 응답 가능해야 함 |
| block index 생성 | canonical markdown line map 또는 IR block 기준으로 block 목록 생성 필요 |
| ETag 생성 규칙 | canonical markdown artifact 버전 식별자 생성 규칙 필요 |
| 응답 모델 | FastAPI/Pydantic response model 정의 필요 |
| 상태 검증 | `completed` 상태만 다운로드 허용 |

현재 코드 기준 선행 준비 상태:

- canonical markdown artifact 저장: 완료
- canonical markdown 파일명 저장: 완료
- run manifest 저장: 완료
- export API response model 초안: 준비 완료
- 문서 계약 정리: 완료
- 실제 endpoint 및 service 구현: 다음 단계

---

## 8. 한 줄 요약

MarkBridge는 문서 목록 API와 문서/블록 다운로드 API를 통해 chunking 시스템이 전체 markdown 기준 또는 canonical block 기준으로 parser 결과를 수집할 수 있게 한다.
