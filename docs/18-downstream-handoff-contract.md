# Downstream Handoff Contract

이 문서는 parser 서버와 chunk 서버 간 Markdown handoff API 계약을 정의한다.

현재 목적은 단순하다.

- parser 서버는 최종 Markdown 1개를 제공한다.
- chunk 서버는 parser 서버에서 해당 Markdown를 pull 한다.
- 내부 `run_id`, `result.md`, `final_resolved.md` 구조는 외부 계약에서 숨긴다.

대상 독자:

- chunker 개발자
- embedding worker 개발자
- parser 서버 개발자

## 1. 핵심 원칙

- 외부 계약은 문서 단위 `document_id` 기준이다.
- chunk 서버는 parser 서버의 로컬 파일시스템에 직접 접근하지 않는다.
- chunk 서버는 최종 Markdown 1개만 받으면 된다.
- parser 내부에서 source/resolved 중 무엇을 canonical 로 선택했는지는 parser 서버 책임이다.
- chunk 서버는 API 응답의 `markdown_download_url` 만 따라가면 된다.

## 2. 외부 식별자와 상태값

### 2.1 식별자

- `document_id`
  - parser 서버가 외부에 노출하는 문서 식별자
  - 예: `doc_af621b8736a2`
- `document_name`
  - 원본 문서 파일명
  - 예: `300233_계약관계자변경.docx`
- `canonical_markdown_name`
  - chunk 서버가 실제로 받게 되는 최종 Markdown 파일명
  - 예: `300233_계약관계자변경.docx-1.md`

중요:

- 내부 구현에서는 여전히 `run_id` 기반 artifact 디렉터리를 가질 수 있다.
- 하지만 외부 API 계약에서는 `run_id` 대신 `document_id`를 사용한다.

### 2.2 상태값

외부 상태 필드는 `status`가 아니라 `parse_status`를 사용한다.

허용값:

- `completed`
- `running`
- `pending`
- `failed`

의미:

- `completed`
  - chunk 서버가 다운로드 가능한 상태
- `running`
  - parser가 아직 처리 중인 상태
- `pending`
  - 아직 처리 시작 전 또는 큐 대기 상태
- `failed`
  - 마지막 파싱이 실패한 상태

## 3. API 목록

현재 v1 계약은 아래 endpoint를 사용한다.

1. `GET /exports/parse-markdown`
2. `GET /exports/parse-markdown/{document_id}/content`
3. `GET /exports/parse-markdown/{document_id}/blocks`
4. `GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content`

## 4. Run List API

`GET /exports/parse-markdown`

설명:

- chunk 서버가 신규 또는 변경된 Markdown export 목록을 조회하는 API
- parser 서버는 각 문서의 최신 parse 결과를 문서 단위로 반환한다.

### 4.1 Query Parameters

- `updated_after`
  - optional
  - ISO8601 UTC timestamp
  - 이 시각 이후에 완료되거나 갱신된 문서만 조회
- `limit`
  - optional
  - integer
  - default `100`
- `cursor`
  - optional
  - opaque string cursor
  - 다음 페이지 조회 위치
- `parse_status`
  - optional
  - `completed`, `running`, `pending`, `failed`
  - 특정 parse 상태만 필터링

### 4.2 Response Example

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
    }
  ],
  "next_cursor": "2026-04-15T02:53:39Z"
}
```

### 4.3 Response Field Definition

- `items`
  - 조회된 parse markdown 문서 목록
- `items[].document_id`
  - 외부 문서 식별자
- `items[].document_name`
  - 원본 파일명
- `items[].canonical_markdown_name`
  - 최종 Markdown 파일명
- `items[].parse_status`
  - `completed`, `running`, `pending`, `failed`
- `items[].last_parse_completed_at`
  - 마지막 성공 완료 시각
- `items[].markdown_download_url`
  - Markdown 본문 다운로드 API path
- `next_cursor`
  - 다음 polling에서 `cursor` 또는 `updated_after` 기준으로 사용할 값

## 5. Content Download API

`GET /exports/parse-markdown/{document_id}/content`

설명:

- chunk 서버가 해당 문서의 최신 canonical Markdown를 다운로드하는 API
- parser 내부적으로 `result.md` 또는 `final_resolved.md` 중 무엇을 사용했는지는 숨긴다.

### 5.1 Path Parameter

- `document_id`
  - 예: `doc_af621b8736a2`

### 5.2 Response Headers Example

- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: attachment; filename="<canonical_markdown_name>"`
- `ETag: "<artifact version>"`
- `Last-Modified: Tue, 15 Apr 2026 02:53:39 GMT`

### 5.3 Response Body Example

실제 구현은 JSON wrapper 대신 raw `text/markdown` body 를 반환하는 것을 권장한다.

Reference wrapper example:

```json
{
  "document_id": "doc_af621b8736a2",
  "document_name": "300233_계약관계자변경.docx",
  "canonical_markdown_name": "300233_계약관계자변경.docx-1.md",
  "content_type": "text/markdown; charset=utf-8",
  "content": "## 1) 계약자변경 유의사항 및 공통사항\n> 계약자 변경 시 유의사항"
}
```

```md
## 1) 계약자변경 유의사항 및 공통사항
> 계약자 변경 시 유의사항

## 3) 계약자 변경 구비서류
| 접수방법 |  | 구비서류 안내 |
| --- | --- | --- |
| 우편/ FC방문 접수 |  | ... |
```

## 6. Chunk 서버 처리 규칙

chunk 서버는 아래 규칙만 따르면 된다.

1. `GET /exports/parse-markdown` 으로 목록 조회
2. `updated_after`, `cursor`, `limit`, `parse_status` 조건 반영
3. `parse_status=completed` 인 문서만 처리
4. 아직 처리하지 않은 문서면 `markdown_download_url` 로 Markdown 다운로드
5. 다운로드한 Markdown를 chunking
6. 마지막 `next_cursor` 저장

중요:

- chunk 서버는 parser 내부의 `run_id`를 몰라도 된다.
- chunk 서버는 `result.md`와 `final_resolved.md` 구분을 몰라도 된다.
- chunk 서버는 `markdown_download_url` 기준으로만 동작하면 된다.

## 7. Canonical Block API

Markdown 전체를 한 번에 chunking 하지 않고 parser가 정리한 canonical block 경계를 직접 쓰고 싶으면 block API를 사용한다.

원칙:

- `content` API는 전체 canonical Markdown 1개를 준다.
- `blocks` API는 canonical Markdown을 구성하는 block 목록과 block별 metadata를 준다.
- block 경계는 parser가 확정한 구조를 그대로 반영한다.
- chunk 서버는 필요에 따라 전체 Markdown 기준 chunking 또는 block 기준 chunking 중 하나를 선택할 수 있다.

### 7.1 Block List API

`GET /exports/parse-markdown/{document_id}/blocks`

설명:

- 특정 문서의 canonical block 목록을 조회하는 API
- 각 block은 parser가 최종 canonical Markdown을 만들 때 사용한 구조 단위다.

Response Example:

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

Field Definition:

- `block_id`
  - block 식별자
- `block_index`
  - 문서 내 canonical 순서
- `block_kind`
  - 예: `heading`, `paragraph`, `list`, `table`, `note`, `warning`
- `markdown_line_start`
  - canonical markdown 기준 시작 줄
- `markdown_line_end`
  - canonical markdown 기준 끝 줄
- `page_number`
  - source anchor가 있으면 원본 페이지 번호
- `block_download_url`
  - 개별 block markdown 다운로드 URL
- `chunk_boundary_candidate`
  - parser가 chunk boundary 후보로 본 block인지 여부

### 7.2 Block Content Download API

`GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content`

설명:

- 개별 canonical block의 Markdown 본문을 다운로드하는 API
- chunk 서버가 특정 block만 재처리하거나 block 단위 chunking을 할 때 사용한다.

Response Headers Example:

- `Content-Type: text/markdown; charset=utf-8`
- `Last-Modified: Tue, 15 Apr 2026 02:53:39 GMT`

Response Body Example:

```md
## 1) 계약자변경 유의사항 및 공통사항
```

또는:

```md
> 계약자 변경 시 유의사항
> 본인 확인이 필요한 경우 추가 서류를 제출해야 합니다.
```

## 8. Canonical Block 사용 규칙

block API는 아래 경우에만 추가로 쓰는 것을 권장한다.

- chunk 경계를 parser 구조 기준으로 직접 맞추고 싶은 경우
- heading, table, note 단위로 chunk를 강제 분리하고 싶은 경우
- 특정 block만 재다운로드해서 부분 재색인을 하고 싶은 경우
- line map과 함께 block-level source anchor를 유지하고 싶은 경우

반대로 아래 경우에는 전체 Markdown API만으로 충분하다.

- 문단 분리만으로도 chunk 품질이 충분한 경우
- parser 구조를 downstream이 별도로 쓰지 않는 경우
- 단순 ingest 파이프라인이 필요한 경우

## 9. Chunk 서버 처리 패턴

### 9.1 단순 Markdown pull 방식

1. `GET /exports/parse-markdown`
2. `updated_after`, `cursor`, `limit`, `parse_status` 조건 반영
3. `parse_status=completed` 인 문서 선택
4. `markdown_download_url`로 전체 Markdown 다운로드
5. downstream이 자체 chunking

### 9.2 Canonical block pull 방식

1. `GET /exports/parse-markdown`
2. `updated_after`, `cursor`, `limit`, `parse_status` 조건 반영
3. `parse_status=completed` 인 문서 선택
4. `GET /exports/parse-markdown/{document_id}/blocks`
5. `block_kind`, `chunk_boundary_candidate`, line range를 보고 chunk 계획 수립
6. 필요 시 `GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content`로 block 본문 다운로드
7. block 단위 또는 block 묶음 단위로 chunking

## 10. Chunk 서버 사용 예시

### 10.1 목록 조회

```bash
curl "http://parser-a:8000/exports/parse-markdown?updated_after=2026-04-15T00:00:00Z&limit=100&parse_status=completed"
```

예시 응답:

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
    }
  ],
  "next_cursor": "2026-04-15T02:53:39Z"
}
```

### 10.2 Markdown 다운로드

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/content" \
  -o "300233_계약관계자변경.docx-1.md"
```

### 10.3 Block 목록 조회

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/blocks"
```

### 10.4 개별 block 다운로드

```bash
curl "http://parser-a:8000/exports/parse-markdown/doc_af621b8736a2/blocks/block-0003/content" \
  -o "doc_af621b8736a2-block-0003.md"
```

## 11. Chunk 서버 Python 예시

```python
import requests

PARSERS = [
    "http://parser-a:8000",
    "http://parser-b:8000",
]

cursor_by_server = {
    "http://parser-a:8000": "2026-04-15T00:00:00Z",
    "http://parser-b:8000": "2026-04-15T00:00:00Z",
}

processed = set()

for base_url in PARSERS:
    response = requests.get(
        f"{base_url}/exports/parse-markdown",
        params={
            "updated_after": cursor_by_server[base_url],
            "limit": 100,
            "parse_status": "completed",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    for document in payload["items"]:
        key = (
            document["document_id"],
            document["last_parse_completed_at"],
        )
        if document["parse_status"] != "completed":
            continue
        if key in processed:
            continue

        md_response = requests.get(
            f"{base_url}{document['markdown_download_url']}",
            timeout=30,
        )
        md_response.raise_for_status()
        markdown = md_response.text

        chunks = chunk_markdown(markdown)
        save_chunks(document, chunks)
        processed.add(key)

    if payload.get("next_cursor"):
        cursor_by_server[base_url] = payload["next_cursor"]
```

block 기반으로 처리하고 싶으면 아래처럼 확장할 수 있다.

```python
blocks_response = requests.get(
    f"{base_url}/exports/parse-markdown/{document['document_id']}/blocks",
    timeout=30,
)
blocks_response.raise_for_status()
blocks_payload = blocks_response.json()

for block in blocks_payload["blocks"]:
    if block["block_kind"] == "heading":
        continue
    block_md = requests.get(
        f"{base_url}{block['block_download_url']}",
        timeout=30,
    ).text
    save_block_chunk(document, block, block_md)
```

## 12. Chunk 서버 구현 포인트

- 최소 구현 기준 dedupe key는 아래 둘 중 하나를 권장한다.
  - `(document_id, last_parse_completed_at)`
  - `(document_id, canonical_markdown_name, last_parse_completed_at)`
- `parse_status != completed` 인 문서는 skip 한다.
- parser 서버가 2대 이상이면 서버별 `next_cursor`를 따로 저장한다.
- polling 주기는 초기 1분, 안정화 후 5분 정도를 권장한다.
- block API를 쓸 때는 `block_index` 순서를 canonical order로 간주한다.
- 부분 재색인이 필요하면 `document_id + block_id + last_parse_completed_at` 조합을 권장한다.

## 13. 내부 구현과 외부 계약의 관계

parser 서버 내부에서는 아래가 계속 존재할 수 있다.

- `result.md`
- `final_resolved.md`
- `repair_candidates.json`
- `downstream_handoff.json`
- `manifest.json`
- `trace.json`

하지만 v1 외부 계약에서는 이것들을 직접 노출하지 않는다.

외부에 노출되는 것은:

- 문서 목록
- 문서별 상태
- 최종 Markdown 다운로드 URL
- canonical block 목록
- block별 다운로드 URL

즉 chunk 서버는 내부 artifact 구조에 결합되지 않는다.

## 14. 향후 확장 가능 항목

v1에서는 제외하지만 이후 필요하면 목록 응답에 아래를 추가할 수 있다.

- `review_required`
- `source_uri`
- `issues_count`
- `last_parse_started_at`
- `etag`
- sidecar download URLs

예:

```json
{
  "document_id": "doc_af621b8736a2",
  "document_name": "300233_계약관계자변경.docx",
  "canonical_markdown_name": "300233_계약관계자변경.docx-1.md",
  "parse_status": "completed",
  "last_parse_completed_at": "2026-04-15T02:53:39Z",
  "markdown_download_url": "/exports/parse-markdown/doc_af621b8736a2/content",
  "review_required": false
}
```

block 응답에는 추후 아래를 추가할 수 있다.

- `block_ref`
- `source_span_refs`
- `heading_level`
- `table_id`
- `issue_ids`
- `repair_applied`

## 15. 한 줄 요약

parser 서버는 `GET /exports/parse-markdown` 으로 문서 목록을 제공하고, 각 문서에 대해 `markdown_download_url`을 내려준다.

단순한 downstream은 `GET /exports/parse-markdown/{document_id}/content` 만 쓰면 되고, 구조 기반 downstream은 `GET /exports/parse-markdown/{document_id}/blocks` 와 `GET /exports/parse-markdown/{document_id}/blocks/{block_id}/content` 를 추가로 사용하면 된다.
