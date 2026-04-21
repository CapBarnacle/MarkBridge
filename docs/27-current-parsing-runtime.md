# 27. Current Parsing Runtime Guide

이 문서는 "현재 MarkBridge parsing이 실제로 어떻게 동작하는가"를 코드 기준으로 빠르게 파악하기 위한 운영 문서다.

정책 문서보다 현재 구현에 더 가깝게 설명하며, 현재 runtime에서 실제로 실행되는 흐름과 품질 판단 기준을 정리한다.

## 1. 개요

### 목적

이 문서의 목적은 아래 4가지다.

1. 현재 parsing runtime의 실제 동작을 코드 기준으로 설명
2. 주요 용어를 한 곳에서 정리
3. 파일 포맷별 parsing 동작 차이를 비교 가능하게 정리
4. 품질 측정 기준과 handoff 판단의 근거를 명확히 설명

### 범위

이 문서는 현재 아래 범위를 다룬다.

- source acquisition
- format resolution
- deterministic inspection
- runtime-aware routing
- parser execution
- common IR 생성
- markdown rendering
- validation
- downstream handoff decision
- repair/export 산출물

이 문서는 아래를 상세 설계 대상으로 다루지 않는다.

- downstream chunking
- embedding generation
- retrieval orchestration
- 최종 answer generation

### 한 줄 요약

현재 parsing은 아래 순서로 동작한다.

1. API 또는 CLI에서 소스 획득
2. 포맷 판별
3. deterministic inspection 실행
4. runtime에서 실제 실행 가능한 parser 후보 확인
5. baseline parser 선택
6. 필요하면 LLM routing recommendation을 비교 후보로만 사용
7. parser 실행 후 공통 IR 생성
8. Markdown 렌더링과 line map 생성
9. validation issue 생성
10. handoff decision 계산
11. repair candidate와 export artifact 저장

## 먼저 볼 문서

- 현재 실행 흐름: [27-current-parsing-runtime.md](/home/intak.kim/project/MarkBridge/docs/27-current-parsing-runtime.md)
- routing / handoff 의사결정: [28-parsing-decision-tree.md](/home/intak.kim/project/MarkBridge/docs/28-parsing-decision-tree.md)
- 컨플루언스용 통합 문서: [30-confluence-parsing-guide.md](/home/intak.kim/project/MarkBridge/docs/30-confluence-parsing-guide.md)
- 정책/튜닝 기준: [24-parsing-policy-and-tuning-guide.md](/home/intak.kim/project/MarkBridge/docs/24-parsing-policy-and-tuning-guide.md)
- parser 후보/정책 레지스트리: [07-parser-capability-registry.md](/home/intak.kim/project/MarkBridge/docs/07-parser-capability-registry.md)
- 현재 runtime 활성 상태: [09-runtime-parser-status.md](/home/intak.kim/project/MarkBridge/docs/09-runtime-parser-status.md)

## 진입점

현재 주요 진입점은 아래다.

- API 앱: [src/markbridge/api/app.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/app.py)
- 서비스 계층: [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)
- 파이프라인 오케스트레이터: [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)

실제 parse API:

- `POST /v1/parse/upload`
- `POST /v1/parse/s3`

## 2. 용어 정의

| 용어 | 정의 | 현재 코드 기준 참고 |
|---|---|---|
| Source Acquisition | 업로드 파일 또는 S3 URI에서 parse 대상 파일을 확보하는 단계 | [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py) |
| Document Format | 입력 파일의 논리 포맷. 현재 `pdf`, `docx`, `xlsx`, `doc`, `hwp` | [src/markbridge/shared/ir.py](/home/intak.kim/project/MarkBridge/src/markbridge/shared/ir.py) |
| Inspection | parser 실행 전에 수행하는 저비용 deterministic feature extraction | [src/markbridge/inspection/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/inspection/basic.py) |
| Runtime Status | parser별 `installed`, `enabled`, `route_kind` 상태 정보 | [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py) |
| Baseline Parser | deterministic routing이 우선 선택한 parser | [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py) |
| Parser Override | `parser_hint` 또는 routing recommendation 비교 결과로 선택 parser를 바꾸는 것 | [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py) |
| Preferred Markdown | parser가 직접 만든 markdown을 우선 보존하기 위한 metadata 경로 | [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py) |
| IR | parser 결과를 공통 구조로 표현하는 Intermediate Representation | [src/markbridge/shared/ir.py](/home/intak.kim/project/MarkBridge/src/markbridge/shared/ir.py) |
| Markdown Line Map | markdown line과 block/source ref를 연결하는 매핑 정보 | [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py) |
| Validation Issue | deterministic validation에서 탐지한 품질 문제 레코드 | [src/markbridge/validators/model.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/model.py) |
| Handoff Decision | downstream으로 넘길 수 있는지 판단한 결과. `accept`, `degraded_accept`, `hold` | [src/markbridge/validators/gate.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/gate.py) |
| Route Kind | parser route의 성격. `primary`, `fallback`, `degraded_fallback`, `text_route` 등 | [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py) |
| Quality Signals | parser 결과 비교 및 품질 판단에 쓰는 수치/징후 | [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py) |

## 3. 전체 동작 흐름

### 3.1 Source Acquisition

API는 업로드 파일 또는 S3 URI를 받아 임시 파일 또는 작업 경로에 source를 준비한다.

이 단계에서 같이 정해지는 것:

- `source_kind`
- `source_name`
- `source_uri`
- `document_format`
- `llm_requested`
- `parser_hint`

관련 코드:

- [src/markbridge/api/app.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/app.py)
- [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)

### 3.2 Format Resolution

현재 지원 suffix는 아래다.

- `.pdf`
- `.docx`
- `.xlsx`
- `.doc`
- `.hwp`

포맷 해석은 서비스 계층에서 먼저 이뤄지고, 이후 `PipelineRequest.document_format`으로 파이프라인에 전달된다.

### 3.3 Inspection

inspection은 full parsing이 아니라, routing과 진단을 위한 저비용 deterministic feature extraction 단계다.

관련 코드:

- [src/markbridge/inspection/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/inspection/basic.py)

현재 inspection의 특징:

- OCR을 하지 않는다
- parser를 실제 실행하지 않는다
- parsing 전 리스크와 실행 가능성을 추정한다
- warning을 통해 unsupported 가능성을 미리 드러낸다

### 3.4 Runtime-Aware Routing

routing은 정책 문서만 보지 않고 현재 환경에서 실제 실행 가능한 parser만 선택한다.

관련 코드:

- [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py)

현재 기본 route:

- PDF: `docling` 우선, 없으면 `pypdf`
- DOCX: `python-docx`
- XLSX: `openpyxl`
- DOC: `libreoffice` 우선, 없으면 `antiword`
- HWP: `hwp5txt`

후보가 설치돼 있어도 policy상 비활성인 경우가 있다.

예:

- `pdfplumber`: installed일 수 있지만 현재 `enabled=false`
- `markitdown`: experimental이라 현재 `enabled=false`

### 3.5 LLM Routing Comparison

현재 서비스 계층에서는 `llm_requested=true`여도 추천 parser를 baseline에 곧바로 덮어쓰지 않는다.

관련 코드:

- [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)

현재 동작:

1. baseline parser로 먼저 pipeline 실행
2. LLM recommendation이 있고 baseline과 다르면 추천 parser로 candidate 실행
3. 두 결과의 품질 신호를 비교
4. candidate가 실제로 더 낫다고 판단될 때만 override

### 3.6 Parser Execution

실제 parser 구현은 아래에 있다.

- [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)

parser는 최종적으로 공통 IR을 반환한다.

### 3.7 Rendering

IR은 Markdown과 `markdown_line_map`으로 렌더링된다.

관련 코드:

- [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py)

현재 중요한 포인트:

- parser가 이미 좋은 Markdown을 가진 경우 `preferred_markdown`을 최대한 유지한다
- line map을 같이 만들어 issue와 markdown line을 연결한다
- 이 line map은 export와 block API에서도 재사용된다

### 3.8 Validation

validation은 deterministic rule로 품질 문제를 탐지한다.

관련 코드:

- [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)

현재 검사 항목:

- `empty_output`
- `text_corruption`
- `table_structure`

### 3.9 Handoff Decision

validation 결과는 downstream handoff decision으로 변환된다.

관련 코드:

- [src/markbridge/validators/gate.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/gate.py)
- [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)

현재 기본 규칙:

- error issue가 하나라도 있으면 `hold`
- warning만 있으면 `degraded_accept`
- issue가 없으면 `accept`

추가 규칙:

- 선택된 parser의 `route_kind`가 `degraded_fallback` 또는 `text_route`면 결과를 더 보수적으로 본다
- warning이 없어도 degraded route면 `accept` 대신 `degraded_accept`가 될 수 있다

### 3.10 Repair / Export

pipeline은 validation issue를 기준으로 deterministic repair candidate를 만들고, 서비스 계층은 필요 시 LLM repair도 붙인다.

핵심 산출물:

- markdown
- issues
- trace
- manifest
- repair candidates
- resolved preview 계열 산출물

## 4. 파일 포맷 별 동작 정리

| 포맷 | Inspection 포인트 | 기본 parser | 대체 parser / fallback | 주요 동작 | 품질상 주의점 |
|---|---|---|---|---|---|
| PDF | `page_count`, `text_layer_coverage`, `table_candidate_count` | `docling` | `pypdf` | `docling`은 markdown 중심 추출과 `preferred_markdown` 보존, `pypdf`는 page text 중심 | layout/table/fomula 보존 품질 차이가 큼 |
| DOCX | `heading_style_availability`, `paragraph_count`, `table_count` | `python-docx` | 현재 활성 대체 route 없음 | 문단/표 순서를 따라 IR 생성, heading heuristic 적용 | 스타일 정보 부족 시 heading 복원이 약해질 수 있음 |
| XLSX | `sheet_count`, `merged_cell_count`, `formula_ratio` | `openpyxl` | 현재 활성 대체 route 없음 | sheet heading과 table block 생성, merged/formula 구조 보존 시도 | merged cell 해석과 row width 편차가 품질 이슈로 이어질 수 있음 |
| DOC | route availability 중심 | `libreoffice` | `antiword` | `libreoffice`는 `.doc -> .docx` 변환 후 `python-docx` 재사용, `antiword`는 text fallback | degraded route일 가능성이 높고 handoff가 보수적으로 내려감 |
| HWP | route availability 중심 | `hwp5txt` | 현재 없음 | text route 중심 | 구조 보존보다 text extraction 중심이라 degraded 취급 가능성이 큼 |

### PDF

- 우선 `docling`을 사용한다
- `docling`이 없으면 `pypdf` fallback으로 내려간다
- `docling`은 `preferred_markdown`을 남기며 OCR은 꺼져 있다
- 구조 보존, heading/table/fomula 관련 fidelity는 parser 간 차이가 가장 큰 포맷이다

### DOCX

- `python-docx` 단일 활성 route다
- paragraph와 table의 source order를 따라 block을 만든다
- heading style과 heuristic을 함께 사용한다
- layout table과 data table을 분기한다

### XLSX

- `openpyxl` 단일 활성 route다
- 각 sheet를 heading block처럼 다룬다
- 셀을 table 구조로 보존하며 formula/merge 흔적을 유지하려고 한다
- row width variation이 크면 validation에서 구조 이상으로 판단할 수 있다

### DOC

- `libreoffice` route가 있으면 우선 사용한다
- 이 경우 실제 parsing은 `.docx` 변환 후 `python-docx` 경로를 재사용한다
- `libreoffice`가 없으면 `antiword` text fallback을 사용한다
- `antiword`는 `degraded_fallback` route라 결과 해석을 더 보수적으로 해야 한다

### HWP

- 현재 활성 route가 있으면 `hwp5txt`를 사용한다
- 구조 해석보다는 text route에 가깝다
- `text_route`로 간주되므로 handoff 판단에서 degraded 처리될 수 있다

## 5. 품질 측정 기준

### 5.1 Validation 기준

현재 deterministic validation은 아래 이슈를 만든다.

| 기준 | 설명 | 결과 코드 | 일반적 severity |
|---|---|---|---|
| Empty Output | block도 없고 markdown도 비어 있는 상태 | `empty_output` | `ERROR` |
| Text Corruption | broken glyph, private-use glyph, formula placeholder 탐지 | `text_corruption` | `WARNING` |
| Table Structure | header row 부재 또는 row width variation 이상 | `table_structure` | `WARNING` 또는 `ERROR` |

`text_corruption`에서 현재 탐지하는 대표 신호:

- replacement character
- private-use glyph
- `<!-- formula-not-decoded -->`
- markdown 전체 또는 개별 block 내부의 깨진 텍스트

### 5.2 Routing 비교 품질 신호

LLM recommendation과 baseline parser를 비교할 때는 아래 신호를 사용한다.

| 신호 | 의미 | 품질 해석 방향 |
|---|---|---|
| `heading_count` | heading이 얼마나 살아남았는가 | 높을수록 유리 |
| `long_line_ratio` | line collapse 가능성이 높은 긴 줄 비율 | 낮을수록 유리 |
| `very_long_line_ratio` | 매우 긴 줄 비율 | 낮을수록 유리 |
| `corruption_density` | nonempty line 대비 corruption issue 비율 | 낮을수록 유리 |
| `formula_placeholder_density` | formula placeholder issue 비율 | 낮을수록 유리 |
| `error_count` | validation error 개수 | 낮을수록 유리 |

### 5.3 Handoff 기준

최종 handoff는 아래처럼 해석한다.

| Decision | 의미 | 운영 해석 |
|---|---|---|
| `accept` | blocking issue 없음 | downstream 전달 가능 |
| `degraded_accept` | warning 또는 degraded route 존재 | 전달 가능하지만 품질 주의 필요 |
| `hold` | error 존재 또는 route 부재 | downstream 전달 보류 |

### 5.4 현재 품질 모델의 한계

- 현재 품질 기준은 parser fidelity의 완전한 정답 판정기가 아니다
- visual fidelity를 직접 측정하지 않는다
- 도메인별 semantic correctness를 완전 검증하지 않는다
- OCR 품질 비교는 현재 범위 밖이다

## 6. 현재 문서를 읽는 추천 순서

현재 parsing 구현을 이해하려면 아래 순서가 가장 빠르다.

1. [27-current-parsing-runtime.md](/home/intak.kim/project/MarkBridge/docs/27-current-parsing-runtime.md)
2. [28-parsing-decision-tree.md](/home/intak.kim/project/MarkBridge/docs/28-parsing-decision-tree.md)
3. [30-confluence-parsing-guide.md](/home/intak.kim/project/MarkBridge/docs/30-confluence-parsing-guide.md)
4. [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)
5. [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)
6. [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py)
7. [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
8. [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)
