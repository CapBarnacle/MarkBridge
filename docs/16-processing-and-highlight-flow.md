# MarkBridge Processing And Highlight Flow

이 문서는 MarkBridge가 문서를 파싱해서 Markdown, validation issue, preview highlight를 만드는 전체 흐름을 빠르게 다시 잡기 위한 운영 문서다.

## 1. 목적

MarkBridge는 문서를 곧바로 chunk 하지 않는다. 먼저 문서를 parser별로 읽고, 공통 IR로 정리하고, validation과 handoff 판단을 거친 뒤, source-faithful Markdown을 만든다.  
UI는 이 과정을 검사하기 위한 inspection workspace다.

핵심 출력은 아래 4가지다.

- `markdown`
- `issues`
- `trace`
- `handoff`

최근에는 여기에 아래가 추가됐다.

- `repair_candidates`
- `resolution_summary`
- `llm_diagnostics`

## 2. 전체 처리 흐름

실행 순서:

1. ingest
2. inspection
3. routing
4. parsing
5. normalization
6. validation
7. rendering
8. export

코드 기준 핵심 경로:

- API 진입: [src/markbridge/api/app.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/app.py)
- 서비스 어댑터: [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)
- 파이프라인 오케스트레이션: [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)
- 파서 구현: [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
- Markdown renderer: [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py)
- Validator: [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)

## 3. IR이 하는 일

IR은 `Intermediate Representation`이다.  
PDF, DOCX, XLSX처럼 서로 다른 입력 포맷을 일단 공통 block 구조로 바꿔둔다.

주요 타입:

- `BlockIR`
- `TableBlockIR`
- `TableCellIR`
- `DocumentIR`

코드:

- [src/markbridge/shared/ir.py](/home/intak.kim/project/MarkBridge/src/markbridge/shared/ir.py)

이 구조 덕분에 parser가 달라도 아래 단계는 공통으로 처리할 수 있다.

- validation
- trace emission
- handoff decision
- Markdown rendering

## 4. preferred_markdown 경로

PDF의 `docling`, 일부 `markitdown` 경로는 parser가 이미 괜찮은 Markdown을 만들어준다.  
이 경우 `DocumentIR.metadata["preferred_markdown"]`에 원본 Markdown을 보관하고, UI에는 가능한 한 이 Markdown을 그대로 보여준다.

관련 코드:

- [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)

이 경로의 장점:

- parser가 만든 결과를 더 source-faithful하게 유지
- markdown table, formula placeholder, heading 형식을 덜 망침

이 경로의 단점:

- issue는 IR block 기준으로 생기는데 preview는 parser가 만든 markdown 줄 기준이라, 둘 사이를 다시 연결해야 함

## 5. Validation과 handoff

validator는 아래를 검사한다.

- empty output
- text corruption
- table structure

`text_corruption`은 현재 아래를 잡는다.

- replacement character
- private-use glyph
- `<!-- formula-not-decoded -->`
- table cell 내부의 깨진 glyph

관련 코드:

- [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)

handoff는 downstream으로 넘겨도 되는지에 대한 품질 게이트다.

- `accept`
- `degraded_accept`
- `hold`

관련 코드:

- [src/markbridge/validators/gate.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/gate.py)

## 5.1 routing은 이제 추천이 아니라 비교 기반으로 동작함

과거에는 `llm_requested=true` 이면 LLM routing recommendation이 parser override로 바로 들어갈 수 있었다.

이 구조의 문제:

- 문서 메타 정보만 보고 parser를 바꾸면 실제 markdown 품질이 더 나빠질 수 있음
- 특히 PDF에서 `docling` 과 `pypdf` 는 구조 보존 특성이 크게 다름

현재 구조:

1. deterministic baseline parser를 먼저 정함
2. LLM이 다른 parser를 추천하면 candidate parser를 별도 실행
3. baseline 결과와 candidate 결과를 품질 신호로 비교
4. candidate가 measurably better 할 때만 override
5. 아니면 baseline 유지

현재 비교 신호 예:

- heading count
- long line ratio
- average line length
- corruption density

즉 `routing_recommendation` 과 `routing_selected_parser` 는 다를 수 있다.

이 결과는 API의 `llm_diagnostics` 로 노출된다.

- `routing_baseline_parser`
- `routing_recommendation`
- `routing_selected_parser`
- `routing_override_applied`
- `routing_comparison_preview`

## 6. UI highlight가 만들어지는 원리

UI highlight는 issue가 preview Markdown의 몇 번째 줄에 대응하는지 알아야 한다.

현재 구조:

1. backend가 `markdown`
2. backend가 `markdown_line_map`
3. backend가 `issues`
4. frontend가 `issue.block_ref`, `excerpt.location_hint`를 `markdown_line_map.refs`와 매칭
5. 매칭된 줄에 highlight 적용

프런트 핵심 코드:

- [frontend/src/App.tsx](/home/intak.kim/project/MarkBridge/frontend/src/App.tsx)

응답 모델:

- [src/markbridge/api/models.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/models.py)
- [frontend/src/types.ts](/home/intak.kim/project/MarkBridge/frontend/src/types.ts)

## 7. highlight 누락이 생겼던 이유

문제의 핵심은 `preferred_markdown` 경로였다.

과거 구조:

- parser가 `preferred_markdown` 생성
- renderer가 IR block을 다시 Markdown 줄에 맞춰 순차 exact-match 시도
- 중간 한 줄이 어긋나면 뒤쪽 block refs가 통째로 비어버림

이 증상으로 보였던 현상:

- detect는 되었는데 preview highlight가 일부만 보임
- issue card는 존재하는데 preview 줄에는 매핑 안 됨
- 표 줄, formula placeholder 줄, heading 줄이 섞인 문서에서 누락이 커짐

## 8. 현재 수정된 구조

### 8.1 heuristic line map 보강

renderer가 이제 한 블록 매칭 실패로 뒤 전체가 무너지지 않게 바뀌었다.

- sequential exact-match만 쓰지 않음
- block별 독립 탐색
- heading, list, table row 정규화
- table cell row refs 보존

코드:

- [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py)

### 8.2 explicit markdown line numbers

더 중요한 변경은 `_blocks_from_markdown()`이 block 생성 시 원본 Markdown 줄 번호를 metadata에 저장하도록 바뀐 점이다.

예:

- heading block -> `markdown_line_numbers=[11]`
- list block -> `markdown_line_numbers=[20]`
- table block -> `markdown_line_numbers=[29,30,31]`

이제 renderer는 가능하면 이 explicit line number를 우선 써서 `markdown_line_map`을 만든다.  
즉 재매칭 추정보다 직접 연결을 먼저 쓴다.

코드:

- [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
- [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py)

## 9. 아직 남아있는 한계

현재 구조는 이전보다 훨씬 안정적이지만, 완전한 궁극 해법은 아니다.

남은 한계:

- `preferred_markdown`이 parser 내부에서 block 구조와 크게 다르게 생성되면 explicit mapping이 충분하지 않을 수 있음
- 한 줄에 여러 corruption token이 있을 때 preview는 대표 highlight 하나만 강하게 보일 수 있음
- formula placeholder는 동일 문자열이 반복되므로, issue별 개별 시각 구분은 아직 약함

## 10. 최종적으로 더 좋은 구조

가장 좋은 구조는 parser 또는 renderer 단계에서 `source map`을 명시적으로 만드는 것이다.

예시:

- markdown line 31 -> `block-17`, `table cell r2 c1`
- markdown line 73 -> `block-33`

즉 나중에 추론하지 않고, 생성 시점에 바로 line-to-block map을 보관하는 형태다.

지금 구조는 그 방향으로 가는 중간 단계다.

## 10.1 수식 복원 관점의 추가 구조

깨진 기호 문제는 단순 문자 치환보다 `formula reconstruction` 문제로 다뤄야 한다.

현재 기준:

- validator가 `text_corruption` issue를 만들 때 `corruption_class`를 같이 기록
- 주요 분류:
  - `inline_formula_corruption`
  - `table_formula_corruption`
  - `formula_placeholder`
  - `symbol_only_corruption`
  - `structure_loss`

그리고 repair 단계에서는 `repair_candidates`를 생성한다.

현재 `repair_candidates`는 아래 역할을 한다.

- 실제 본문을 자동 치환하지 않음
- deterministic transliteration 결과를 preview candidate로 제공
- placeholder처럼 deterministic 복원이 어려운 경우 `llm_required`로 표시
- 이후 LLM 복원기나 reviewer UI가 붙을 자리로 사용

이제 candidate는 단순 문자열 제안이 아니라 `patch proposal`도 함께 가진다.

- `origin=deterministic` 또는 `origin=llm`
- `block_ref`, `markdown_line_number`, `location_hint` 보유
- `patch_proposal.action=replace_text`
- `patch_proposal.target_text`
- `patch_proposal.replacement_text`
- `patch_proposal.uncertain`

즉 현재 repair 단계는 "원문 markdown를 직접 변경"하지 않고 "위치가 붙은 reviewable patch"를 생성하는 구조다.

즉 현재 구조는:

1. detect
2. classify
3. candidate propose
4. review
5. optional apply

## 10.2 LLM repair batching

`docling` 같이 구조가 잘 보존되는 parser는 수식 오염 issue를 더 많이 드러낼 수 있다.
이 경우 LLM repair target 수가 급증해서, 한 번의 큰 JSON 요청으로 보내면 truncation 또는 malformed JSON 위험이 커진다.

현재 구조는 large target set을 여러 batch로 나눈다.

1. issue별 prompt item 생성
2. 입력 문자 수와 batch size 기준으로 분할
3. batch별로 LLM repair 호출
4. batch 응답을 합쳐 `generated_candidates` 와 merged repair response 생성
5. batch별 error는 누적해서 diagnostics에 남김

즉 지금의 LLM repair 단계는:

- full-document reconstruction 이 아님
- issue-targeted reconstruction 이고
- target volume이 커지면 batched repair execution 으로 degrade 없이 처리하려는 구조다

순서를 따르도록 설계 중이다.

관련 코드:

- [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)
- [src/markbridge/repairs/formula.py](/home/intak.kim/project/MarkBridge/src/markbridge/repairs/formula.py)
- [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)
- [src/markbridge/api/models.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/models.py)

## 11. 디버깅 순서

하이라이트가 안 보이면 아래 순서로 본다.

1. issue가 실제로 생성됐는지 확인
- `issues.json`
- `ParseResponse.issues`

2. markdown 줄에 문제가 실제로 존재하는지 확인
- `result.md`
- `ParseResponse.markdown`

3. 해당 줄의 `markdown_line_map.refs`가 비어 있는지 확인
- `ParseResponse.markdown_line_map`

4. issue의 `block_ref`, `location_hint`와 line-map ref가 맞는지 확인

5. repair candidate가 기대대로 생성됐는지 확인
- `ParseResponse.repair_candidates`
- corruption class가 formula 계열인지 확인
- placeholder는 `llm_required`로 나오는지 확인

6. UI가 최신 백엔드를 보고 있는지 확인
- `localhost:8000` 재시작 여부
- stale response 여부

유용한 산출물:

- `/tmp/markbridge/<run_id>/result.md`
- `/tmp/markbridge/<run_id>/issues.json`
- `/tmp/markbridge/<run_id>/trace.json`

## 12. 관련 테스트

- [tests/unit/test_markdown_renderer.py](/home/intak.kim/project/MarkBridge/tests/unit/test_markdown_renderer.py)
- [tests/unit/test_validators_execution.py](/home/intak.kim/project/MarkBridge/tests/unit/test_validators_execution.py)

이 테스트들은 아래를 지킨다.

- preferred markdown에서도 line-map refs가 유지되는지
- 중간 mismatch 뒤에 later refs가 안 사라지는지
- table cell corruption이 issue로 잡히는지

## 13. 다음에 더 하면 좋은 것

우선순위 높은 후속 작업:

1. preview 한 줄에 다중 corruption highlight 지원
2. formula placeholder 반복 구간에 issue별 배지 추가
3. parser 단계에서 explicit source map을 더 넓게 생성
4. issue 클릭 시 preview뿐 아니라 table row/cell 단위 focus 강화
