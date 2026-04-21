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

추가로 중요한 점은 "inspection이 항상 일부 페이지만 보는 것은 아니다"는 것이다.

현재 구현 기준:

- PDF inspection은 전체 페이지를 순회하면서 각 페이지에서 `extract_text()`를 호출한다
- DOCX inspection은 문서 전체의 paragraph와 table 목록을 읽는다
- XLSX inspection은 workbook 전체 sheet를 열고, 모든 cell을 순회하면서 non-empty/formula cell을 센다
- DOC와 HWP inspection은 문서 내용을 정밀하게 읽기보다 실행 route의 가능 여부를 확인한다

즉 현재 inspection은 "샘플링 기반"이 아니라, 포맷에 따라 문서 전체를 가볍게 스캔하는 구조다.
다만 여전히 본 parsing에 비해 역할이 제한적이다.

- IR을 만들지 않는다
- markdown를 만들지 않는다
- table normalization이나 heading heuristic 같은 parser 내부 ruleset을 적용하지 않는다
- OCR이나 LLM 호출이 없다

### 3.3.1 포맷별 inspection 실제 동작

| 포맷 | inspection에서 실제로 하는 일 | 문서 전체 읽기 여부 | 현재 비용 특성 |
|---|---|---|---|
| PDF | `PdfReader`로 전체 page list를 읽고 각 page마다 `extract_text()` 호출, text 존재 여부와 `|` 개수를 집계 | 전체 페이지 순회 | 페이지 수가 많을수록 선형적으로 증가 |
| DOCX | `DocxDocument`로 문서를 열고 전체 paragraph 수, table 수, heading style 존재 여부를 계산 | 문서 전체 paragraph/table 목록 사용 | 문단과 표 수에 비례 |
| XLSX | `load_workbook(data_only=False)`로 workbook을 열고 전체 sheet와 cell을 순회하면서 merged/formula/non-empty cell을 계산 | 전체 workbook 순회 | sheet 수와 cell 수가 많을수록 증가 |
| DOC | `libreoffice`, `antiword` 가능 여부만 점검 | 내용 전체를 읽지 않음 | 매우 낮음 |
| HWP | `hwp5txt` 가능 여부만 점검 | 내용 전체를 읽지 않음 | 매우 낮음 |

### 3.3.2 PDF inspection 세부 설명

현재 PDF inspection은 초반 몇 페이지만 보는 방식이 아니다.

실제 동작:

1. `PdfReader`로 PDF를 연다
2. `len(reader.pages)`로 전체 페이지 수를 계산한다
3. 전체 페이지를 순회한다
4. 각 페이지에서 `page.extract_text()`를 호출한다
5. 추출 텍스트가 비어 있지 않으면 text-layer page로 센다
6. 텍스트 안의 `|` 개수를 table candidate signal로 누적한다

현재 계산 결과:

- `page_count`
- `text_layer_coverage`
- `table_candidate_count`
- `complexity_score`

해석:

- page count를 알려면 어차피 전체 page list 접근이 필요하다
- text layer coverage를 계산하려면 현재 구현상 전체 페이지를 다 봐야 한다
- 따라서 현재 PDF inspection은 "전체 PDF를 가볍게 텍스트 스캔"하는 구조다

### 3.3.3 DOCX inspection 세부 설명

현재 DOCX inspection은 일부 paragraph만 샘플링하지 않는다.

실제 동작:

1. `DocxDocument`로 문서를 연다
2. `doc.paragraphs` 전체를 list로 만든다
3. `doc.tables` 길이를 센다
4. paragraph 전체를 돌면서 style name에 `Heading`이 포함되는지 센다

현재 계산 결과:

- `paragraph_count`
- `table_count`
- `heading_style_availability`
- `complexity_score`

해석:

- heading style 존재 여부를 정확히 보려면 전체 paragraph를 확인해야 한다
- 현재 구현은 heading heuristic을 여기서 적용하지 않고, parser 단계에서만 적용한다

### 3.3.4 XLSX inspection 세부 설명

현재 XLSX inspection도 일부 sheet나 일부 row만 보지 않는다.

실제 동작:

1. `load_workbook(data_only=False)`로 workbook을 연다
2. 전체 worksheet 목록을 가져온다
3. 전체 sheet에 대해 merged range 수를 센다
4. 전체 sheet, 전체 row, 전체 cell을 순회한다
5. non-empty cell 수를 센다
6. 문자열 값이 `=`로 시작하는 cell을 formula cell로 센다

현재 계산 결과:

- `sheet_count`
- `merged_cell_count`
- `formula_ratio`
- `complexity_score`

해석:

- formula ratio는 현재 구현상 전체 non-empty cell을 봐야 계산 가능하다
- merged cell 존재 여부와 formula 비율은 이후 routing/품질 해석에 참고 신호로만 쓰인다

### 3.3.5 DOC / HWP inspection 세부 설명

DOC와 HWP는 현재 inspection 단계에서 문서 내용을 깊게 읽지 않는다.

DOC 실제 동작:

- `libreoffice`가 있는지 확인
- `antiword`가 있는지 확인
- 둘 중 하나라도 가능하면 conversion feasibility를 true로 둔다

HWP 실제 동작:

- `hwp5txt`가 있는지 확인
- 있으면 execution feasibility를 true로 둔다

해석:

- 이 둘은 현재 "문서 내부 구조를 읽는 inspection"보다 "실행 route availability check"에 가깝다
- 그래서 PDF, DOCX, XLSX와 달리 내용 기반 feature extraction이 약하다

### 3.3.6 현재 inspection 비용에 대한 해석

현재 inspection은 포맷에 따라 문서 전체를 훑기 때문에 입력 크기가 커질수록 비용이 늘어난다.
다만 현재 비용 특성은 아래처럼 정리할 수 있다.

- OCR 비용 없음
- LLM 비용 없음
- markdown 렌더링 비용 없음
- parser 내부 normalization 비용 없음
- deterministic Python library 호출 위주

즉 "문서 전체를 일부 읽는다"가 아니라 "문서 전체를 비교적 가볍게 스캔한다"에 가깝다.

현재 구현에는 "앞의 3페이지만 inspection" 같은 sampling 기준은 없다.
그런 최적화는 아직 들어가 있지 않다.

### 3.3.7 inspection 결과 중 LLM에 실제로 전달되는 값

inspection은 포맷별로 여러 값을 계산하지만, 현재 LLM routing recommendation prompt에는 그중 일부만 들어간다.

현재 LLM prompt에 들어가는 inspection 기반 값:

- `page_count`
- `sheet_count`
- `complexity_score`

같이 들어가는 비-inspection 값:

- `document_format`
- `source_name`
- `parser_hint`
- `executable_candidates`

현재 inspection 계산값과 LLM 전달값의 차이는 아래와 같다.

| 포맷 | inspection에서 계산하는 값 | 현재 LLM prompt에 실제 전달되는 값 | 현재 전달되지 않는 값 |
|---|---|---|---|
| PDF | `page_count`, `text_layer_coverage`, `table_candidate_count`, `complexity_score` | `page_count`, `complexity_score` | `text_layer_coverage`, `table_candidate_count` |
| DOCX | `paragraph_count`, `table_count`, `heading_style_availability`, `complexity_score` | `complexity_score` | `paragraph_count`, `table_count`, `heading_style_availability` |
| XLSX | `sheet_count`, `merged_cell_count`, `formula_ratio`, `complexity_score` | `sheet_count`, `complexity_score` | `merged_cell_count`, `formula_ratio` |
| DOC | `conversion_feasibility`, `conversion_output_quality_signals` | 직접 전달되는 inspection field는 사실상 없음 | 대부분의 DOC inspection detail |
| HWP | `execution_feasibility`, `execution_route_candidates` | 직접 전달되는 inspection field는 사실상 없음 | 대부분의 HWP inspection detail |

즉 현재 LLM은 inspection 전체를 받는 것이 아니라, 아주 축약된 feature summary만 받는다.

### 3.3.8 complexity_score 계산 방식

`complexity_score`는 현재 포맷별로 매우 단순한 heuristic으로 계산된다.
정규화된 연속 점수라기보다 "복잡한 징후가 있는가"를 나타내는 현재형 signal에 가깝다.

포맷별 현재 계산 방식:

| 포맷 | 현재 계산식 | 의미 해석 |
|---|---|---|
| PDF | `float(table_candidate_count > 0)` | 텍스트 안에 `|`가 하나라도 나오면 `1.0`, 아니면 `0.0` |
| DOCX | `float(table_count > 0)` | 표가 하나라도 있으면 `1.0`, 아니면 `0.0` |
| XLSX | `float(merged_cell_count > 0 or formula_cells > 0)` | merged cell 또는 formula cell이 하나라도 있으면 `1.0`, 아니면 `0.0` |
| DOC | 현재 별도 complexity score 계산 없음 | route feasibility 중심 |
| HWP | 현재 별도 complexity score 계산 없음 | route feasibility 중심 |

해석할 때 주의할 점:

- 현재 `complexity_score`는 세밀한 난이도 점수가 아니다
- 사실상 0 또는 1에 가까운 boolean-style signal이다
- PDF에서 표 후보가 하나만 있어도 1.0이 된다
- DOCX에서 단순한 표 하나만 있어도 1.0이 된다
- XLSX에서 formula cell 하나만 있어도 1.0이 된다

즉 현재 LLM routing prompt에서 `complexity_score`는 "이 문서가 구조적으로 단순한 축에 가까운가, 아니면 표/수식/merge 신호가 있는가" 정도만 전달하는 값으로 이해하는 것이 맞다.

### 3.3.9 현재 LLM routing recommendation의 유효성과 한계

현재 구조에서 LLM routing recommendation은 "최종 parser 선택기"라기보다 "보조 추천기"에 가깝다.

이유:

- LLM이 문서 원문 전체를 보지 않는다
- parser output을 보지 않는다
- validation 결과를 보지 않는다
- inspection 전체가 아니라 축약된 feature summary만 본다
- `complexity_score`도 정밀 점수가 아니라 매우 거친 heuristic이다

따라서 현재 LLM 추천 자체의 정보력은 제한적이다.
특히 아래 같은 한계가 있다.

- PDF의 `text_layer_coverage`와 `table_candidate_count`가 현재 prompt에 직접 안 들어간다
- DOCX의 `paragraph_count`, `table_count`, `heading_style_availability`가 직접 안 들어간다
- XLSX의 `merged_cell_count`, `formula_ratio`가 직접 안 들어간다
- `complexity_score`가 0/1에 가까운 boolean-style signal이라 문서 간 미세한 차이를 잘 반영하지 못한다

그럼에도 현재 구조가 운영상 어느 정도 유효한 이유는, 추천을 그대로 적용하지 않기 때문이다.

현재 실제 동작:

1. baseline parser를 먼저 실행한다
2. LLM이 다른 parser를 추천하면 candidate parser도 실제로 실행한다
3. 두 결과를 quality signal로 비교한다
4. candidate가 실제로 더 좋을 때만 override를 적용한다

즉 현재 설계는 아래처럼 해석하는 것이 맞다.

- LLM 추천 자체의 유효성: 제한적
- LLM 추천을 포함한 전체 routing 구조의 유효성: 비교적 합리적

한 문장으로 정리하면:

현재 LLM routing은 "정밀한 추천 엔진"이라기보다 "추가 비교 후보를 제안하는 약한 추천기"이며, 최종 신뢰는 parser 실제 실행 결과 비교에서 확보한다.

### 3.3.10 baseline parser와 candidate parser의 품질 평가 방식

LLM routing이 개입하더라도 최종 override 판단은 추천 자체가 아니라 실제 parser 실행 결과 비교로 내려진다.

현재 비교 순서:

1. baseline parser 실행
2. candidate parser 실행
3. 각 parser 결과의 markdown와 validation issue를 읽음
4. 품질 요약값을 계산
5. candidate가 실제로 더 좋다고 판단될 때만 override 적용

즉 inspection 단계의 추정치가 아니라, 실제 parser output 기반 비교다.

현재 품질 요약에서 보는 신호:

| 신호 | 의미 | 일반적 해석 |
|---|---|---|
| `heading_count` | markdown에서 heading line 수 | 높을수록 구조 보존에 유리 |
| `average_line_length` | 평균 line 길이 | 지나치게 길면 구조 붕괴 가능성 증가 |
| `long_line_count` | 180자 이상 line 개수 | 많을수록 불리 |
| `very_long_line_count` | 400자 이상 line 개수 | 많을수록 더 불리 |
| `long_line_ratio` | 180자 이상 line 비율 | 낮을수록 유리 |
| `very_long_line_ratio` | 400자 이상 line 비율 | 낮을수록 유리 |
| `text_corruption_issue_count` | `text_corruption` issue 수 | 낮을수록 유리 |
| `private_use_count` | private-use glyph 수 | 낮을수록 유리 |
| `formula_placeholder_count` | formula placeholder issue 수 | 낮을수록 유리 |
| `corruption_density` | non-empty line 대비 corruption issue 비율 | 낮을수록 유리 |
| `formula_placeholder_density` | non-empty line 대비 formula placeholder 비율 | 낮을수록 유리 |
| `error_count` | validation error 수 | 낮을수록 유리 |

현재 점수 해석 방식:

- score는 100점 기준에서 시작하는 heuristic score다
- error가 있으면 큰 감점
- corruption density가 높으면 큰 감점
- formula placeholder density가 높으면 추가 감점
- private-use glyph가 많으면 감점
- long line / very long line 비율이 높으면 감점
- heading이 적절히 살아 있으면 가점
- non-empty line이 충분한데 heading이 전혀 없으면 감점

즉 현재 품질 모델은 아래 성향을 가진다.

- 구조가 잘 살아 있는 markdown를 선호
- line collapse가 적은 결과를 선호
- 깨진 glyph와 formula placeholder가 적은 결과를 선호
- validation error가 없는 결과를 강하게 선호

현재 override 판단의 성격:

- 단순히 candidate score가 baseline score보다 약간 높다고 바로 뒤집지 않는다
- candidate가 실제로 더 낫다고 볼 수 있는지 보수적으로 판단한다
- error, corruption, line collapse, heading 보존을 종합적으로 본다

따라서 현재 비교 로직은 "정답 판정기"라기보다 "운영상 방어 가능한 heuristic comparator"로 이해하는 것이 맞다.

현재 장점:

- LLM 추천을 맹신하지 않는다
- 실제 parser 결과를 기준으로 비교한다
- 구조 보존과 corruption을 동시에 본다

현재 한계:

- visual fidelity를 직접 측정하지 않는다
- 표 의미 보존을 완전하게 점수화하지 못한다
- heading 수가 많다고 항상 더 좋은 것은 아니다
- line length 기반 지표는 문서 성격에 따라 과벌점 가능성이 있다

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

### 3.7.1 markdown 렌더링이란 무엇인가

markdown 렌더링은 parser가 만든 공통 IR을 최종 markdown 문자열로 바꾸는 단계다.

입력:

- `DocumentIR`
- 그 안의 `BlockIR`
- `TableBlockIR`
- `TableCellIR`

출력:

- 최종 markdown 텍스트

현재 block별 기본 동작:

- heading block -> `#`, `##` 등의 heading line으로 렌더링
- paragraph block -> 일반 문단 텍스트로 렌더링
- note block -> `>` note line으로 렌더링
- table block -> markdown table로 렌더링

### 3.7.2 preferred_markdown 경로

모든 markdown가 renderer에서 새로 조립되는 것은 아니다.

현재 parser 중 일부는 parser가 직접 만든 markdown를 `DocumentIR.metadata["preferred_markdown"]`에 넣는다.

대표 예:

- `docling`
- `antiword`
- `hwp5txt`

이 경우 renderer는 block을 다시 조립하기보다, parser가 만든 markdown를 우선 그대로 사용한다.

즉 현재 렌더링 경로는 두 가지다.

1. parser가 만든 `preferred_markdown` 재사용
2. IR block을 순서대로 렌더링해서 markdown 생성

### 3.7.3 line map이란 무엇인가

line map은 최종 markdown의 각 줄이 어떤 block/source와 연결되는지 기록한 매핑 정보다.

현재 line map entry에는 대략 아래 정보가 들어간다.

- `line_number`
- `text`
- `refs`
- `page_number` 가능 시 포함

여기서 핵심은 `refs`다.

예:

- `block-3`
- `table cell r2 c4`

즉 markdown 한 줄이 어떤 block 또는 table cell과 연결되는지 추적할 수 있게 만든다.

### 3.7.4 line map이 왜 필요한가

line map이 없으면 validation issue를 "어떤 markdown 줄에서 발생했는지" 연결하기 어렵다.

현재 line map은 아래 용도로 중요하다.

- validation issue를 markdown 줄과 연결
- UI highlight 위치 계산
- block export API에서 markdown 범위 계산
- page hint를 줄 단위로 전달

즉 markdown는 사람이 읽는 출력이고, line map은 그 출력의 추적성과 설명 가능성을 보강하는 sidecar다.

### 3.7.5 현재 line map 생성 방식

현재 renderer는 두 가지 방식으로 line map을 만든다.

1. explicit metadata 기반
2. heuristic matching 기반

explicit metadata 기반:

- block metadata에 `markdown_line_numbers`가 있으면
- 그 줄 번호를 그대로 사용해 refs를 붙인다

이 방식이 가장 강하다.

heuristic matching 기반:

- explicit line number가 없거나 불완전하면
- renderer가 block을 렌더링한 expected line과 실제 markdown line을 비교해 가장 비슷한 줄을 찾는다

즉 preferred markdown를 그대로 쓰는 경우에도 line map은 별도로 다시 연결해야 한다.

### 3.7.6 table 렌더링과 line map의 특수성

table block은 일반 paragraph보다 더 많은 추적 정보가 필요하다.

현재 table 렌더링 시:

- markdown table line 생성
- header line 생성
- separator line 생성
- row별 line 생성
- row에 해당하는 cell refs를 함께 line map에 기록

또한 merged cell signal이 있는 complex table은 table 앞에 안내 line을 추가할 수 있다.

예:

- `[Complex table preserved: table-id]`

즉 table line map은 단순히 "표 전체 block"만 가리키는 것이 아니라, 가능한 경우 row/cell 수준 ref까지 함께 갖는다.

### 3.8 Validation

validation은 deterministic rule로 품질 문제를 탐지한다.

관련 코드:

- [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)

현재 검사 항목:

- `empty_output`
- `text_corruption`
- `table_structure`

### 3.8.1 validation은 누가 수행하는가

현재 validation은 LLM이 아니라 deterministic validator 코드가 수행한다.

실행 주체:

- [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)의 `validate_document()`

호출 주체:

- [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)

즉 parser와 renderer가 끝난 뒤, pipeline이 validation을 호출한다.

### 3.8.2 validation은 언제 수행되는가

현재 순서는 아래와 같다.

1. parser가 `DocumentIR` 생성
2. renderer가 markdown 생성
3. `validate_document(document, markdown_text=...)` 호출
4. `ValidationReport` 생성
5. handoff decision 계산
6. repair candidate 생성

즉 validation은 parser 이전이 아니라 parser 결과 이후에 수행되는 사후 품질 검사다.

### 3.8.3 validation 입력은 무엇인가

현재 validator는 아래 두 가지를 같이 받는다.

- `DocumentIR`
- `markdown_text`

이유:

- 어떤 문제는 block 구조에서 더 잘 보인다
- 어떤 문제는 최종 markdown 텍스트에서 더 잘 보인다

즉 현재 validation은 구조 기반 검사와 렌더링 결과 기반 검사를 함께 수행한다.

### 3.8.4 현재 validation이 실제로 하는 검사

현재 `validate_document()`는 크게 세 종류 검사를 수행한다.

1. `_check_empty_output`
2. `_check_text_corruption`
3. `_check_table_structure`

#### empty output 검사

조건:

- `document.blocks`가 비어 있고
- `markdown_text.strip()`도 비어 있음

결과:

- `empty_output` issue 생성
- severity는 `ERROR`

의미:

- parser가 사실상 문서를 비워서 내보낸 상태

#### text corruption 검사

현재 validation의 핵심 검사다.

현재 보는 대표 신호:

- replacement character `�`
- private-use glyph
- `<!-- formula-not-decoded -->`

검사 방식:

- 먼저 document block 내부 텍스트를 순회
- block 기준으로 못 찾은 경우 markdown 전체도 검사

즉 block 구조와 최종 markdown 출력을 둘 다 본다.

현재 이 검사는 단순 탐지로 끝나지 않고 corruption class도 붙인다.

대표 corruption class:

- `symbol_only_corruption`
- `inline_formula_corruption`
- `table_formula_corruption`
- `formula_placeholder`
- `structure_loss`

이 분류는 이후 repair candidate 생성에도 직접 연결된다.

#### table structure 검사

현재 `TableBlockIR`에 대해 수행된다.

현재 보는 기준:

- header row가 비어 있는가
- row width variation이 비정상적인가

예:

- 첫 row에 non-empty header cell이 전혀 없으면 `table_structure` warning
- row별 cell 개수 편차가 과도하면 `table_structure` warning 또는 error

현재 merged cell signal이 있거나 markdown table source인 경우에는 경고 쪽으로 완화해서 본다.

### 3.8.5 validation issue에는 무엇이 담기는가

현재 issue는 단순 문자열이 아니라 구조화된 레코드다.

대표 필드:

- `issue_id`
- `code`
- `severity`
- `message`
- `location`
- `excerpts`
- `details`
- `repairable`

예를 들어 text corruption issue에는 아래 같은 정보가 같이 들어갈 수 있다.

- highlight 대상 문자열
- 주변 excerpt
- replacement char 개수
- private-use glyph 개수
- corruption class

즉 validation은 단순 fail/pass가 아니라, 이후 trace, UI highlight, repair 단계에서 재사용할 수 있는 상세 evidence를 남긴다.

### 3.8.6 validation 결과는 어떻게 사용되는가

validation 결과는 `ValidationReport`로 묶인다.

여기에는 보통 아래가 들어간다.

- `issues`
- `summary`

summary 대표 항목:

- `issue_count`
- `error_count`
- `warning_count`

이 결과는 이후 아래 단계에 바로 연결된다.

- trace emission
- handoff decision
- repair candidate generation

### 3.8.7 validation과 handoff의 연결

현재 handoff는 [src/markbridge/validators/gate.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/gate.py)의 `evaluate_handoff()`가 계산한다.

기본 규칙:

- error issue가 하나라도 있으면 `hold`
- warning만 있으면 `degraded_accept`
- issue가 없으면 `accept`

그리고 orchestrator가 route kind를 한 번 더 반영한다.

예:

- `degraded_fallback`
- `text_route`

이런 route는 issue가 적어도 결과를 더 보수적으로 본다.

즉 validation은 단순 리포트가 아니라 downstream 전달 여부를 결정하는 핵심 입력이다.

### 3.8.8 현재 validation의 역할과 한계

현재 validation의 역할:

- parser 결과가 비었는지 검사
- 깨진 glyph, formula placeholder, table 구조 이상을 탐지
- traceable issue record 생성
- handoff와 repair 단계 입력 제공

현재 한계:

- visual fidelity를 직접 검사하지 않는다
- 표 의미 보존을 완전하게 검증하지 않는다
- 도메인 semantic correctness를 완전하게 판단하지 않는다
- heuristic 기반이라 false positive / false negative 가능성이 있다

즉 현재 validation은 "문서가 완벽한지 증명"하는 단계가 아니라, 운영상 필요한 blocking/degraded 신호를 deterministic하게 생성하는 단계다.

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
