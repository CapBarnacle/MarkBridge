# Resume Brief

이 문서는 다음 세션에서 빠르게 재개하기 위한 짧은 브리프다.

## 현재 상태

- 프로젝트 목표가 다시 정리됨
  - 문서별 최적 parser 조합 선택
  - 파싱 중 단계별 모니터링
  - 파싱 후 issue 최대 복구
  - 최종 복구된 markdown 를 downstream

- backend parse / trace / issue / markdown preview 흐름은 연결 완료
- `preferred_markdown` 경로에서도 `markdown_line_map`이 explicit line number 기반으로 강화됨
- preview highlight 누락은 renderer/source-map 구조를 보강해서 이전보다 안정화됨
- `text_corruption` issue는 이제 수식 관점 taxonomy를 가짐
  - `inline_formula_corruption`
  - `table_formula_corruption`
  - `formula_placeholder`
  - `symbol_only_corruption`
  - `structure_loss`
- repair 단계에서 `repair_candidates` 생성
  - deterministic transliteration + review 목적
  - placeholder는 `llm_required`
- API/service 레이어에서 `repair_candidates`가 line-aware patch proposal 형태로 보강됨
  - `origin`
  - `block_ref`
  - `markdown_line_number`
  - `patch_proposal`
- `llm_requested=true` 이고 설정이 있으면 formula-like issue에 대해 별도 `origin=llm` candidate가 추가됨
- 현재 정책은 아직 `source markdown` 중심이라, 목표와 완전히 일치하지는 않음
  - 현재는 `suggested_resolved.md` 가 preview 성격
  - 다음 단계에서 `final resolved markdown` canonicalization 정책으로 전환해야 함
- run artifact 저장 파일
  - `repair_candidates.json`
  - `llm_formula_repair.json`
  - `first_formula_probe.json`
  - `first_formula_probe_page.png`
  - `first_formula_probe_region.png`
  - `suggested_resolved.md`
  - `suggested_resolved_patches.json`
  - `final_resolved.md`
  - `final_resolved_patches.json`
  - `downstream_handoff.json`
  - `parse_evaluation.json`
  - downstream 전달 단순화를 위한 canonical markdown 파일
    - 원본 전체 파일명 기준 예: `300233_계약관계자변경.docx-1.md`
    - 내부적으로는 `downstream_handoff.preferred_markdown_kind` 를 따라 source/resolved 중 하나를 선택
- API 응답에 `repair_candidates` 포함
- API 응답에 `suggested_resolved_markdown`, `suggested_resolved_patches` 포함
- API 응답에 `final_resolved_markdown`, `final_resolved_patches` 포함
- API 응답에 `downstream_handoff` 포함
- API 응답에 `evaluation` 포함
- API 응답에 `resolution_summary` 포함
  - issue별 `resolved`, `selected_origin`, `llm_requested`, `llm_attempted`, `unresolved_reason`
  - issue별 `selected_confidence`, `selection_reason`, `candidate_decisions`
- API 응답에 `llm_diagnostics` 포함
  - `formula_probe_attempted`
  - `formula_probe_apply_as_patch`
  - `formula_probe_confidence`
  - `formula_probe_region_image_path`
  - `formula_probe_preview`
  - 집계별 `unresolved_by_class`, `unresolved_by_reason`
- API 응답에 `llm_diagnostics` 포함
  - `routing_used`
  - `routing_recommendation`
  - `repair_attempted_issues`
  - `repair_generated_candidates`
  - `repair_error`
  - `repair_response_available`
  - `repair_response_preview`
- UI 타입 정의에 `repair_candidates` 반영
- UI issue panel에 repair candidate 카드 표시 추가
  - deterministic base / LLM proposal 구분
  - patch proposal replace/with 표시
- preview panel에서 `Source` / `Final resolved` 토글 가능
- preview panel에서 실제 downstream 기준 markdown 이 source/resolved 중 무엇인지 배너로 표시
- trace panel에서 downstream handoff 정책 카드 표시
- trace panel에서 recovery flow 요약 표시
  - `detected`
  - `deterministic recovered`
  - `LLM attempted`
  - `LLM recovered`
  - `resolved`
  - `unresolved`
- trace panel의 LLM assist 카드에서 `routing` 과 `repair` 를 분리해 표시
  - `Routing`
  - `Repair`
- frontend 는 이제 notes 파싱보다 `llm_diagnostics` 를 우선 사용
- LLM assist 카드에서 repair raw response preview 일부를 직접 표시
- backend notes 에 아래 항목 추가
  - `llm_repair_attempted_issues`
  - `llm_repair_generated_candidates`
  - `llm_repair_error`
- evaluation panel에서 readiness score / next step 확인 가능
- evaluation panel에서 unresolved class / unresolved reason / issue-level resolution 상태 확인 가능
- repair card에 `detected -> deterministic -> llm -> resolved preview -> downstream` 처리 경로 표시
- repair card에 candidate별 `Selected winner` / `Rejected` 와 selection/rejection reason 표시
- unresolved reason에 `selected_patch_not_applied` 추가
  - winner candidate는 있었지만 source markdown에 안전하게 적용되지 않은 경우를 별도 구분
- 현재 downstream 정책은 recovery 성공 시 `preferred_markdown_kind=resolved`
- live 검증에서 table formula sample 은 `resolved_preferred` 와 `ready` 상태까지 확인됨
- deterministic candidate가 충분히 구조화된 경우 `llm_recommended=false` 로 분류됨
  - 현재는 `q_{x+t}^{L}` 류처럼 구조가 복원된 케이스를 strong baseline으로 간주
- benchmark / 평가 기준 문서 추가
- 전체 delivery/architecture overview 문서 추가

- deterministic formula repair가 강화됨
  - inline actuarial notation의 `q x+t l` 류를 `q_{x+t}^{L}` 형태까지 보수적으로 정규화
  - table formula corruption도 이전보다 더 나은 candidate 생성

- recent DOCX regression 대응 반영
  - `1)`, `2)`, `3)` 류 닫힌 번호 문단이 heading 으로 승격됨
  - `①`, `②`, `③` 류 원형 숫자 문단은 문맥상 섹션 제목일 때만 heading 으로 승격됨
  - single-column DOCX layout table 은 plain paragraph 로 완전 평탄화하지 않고 note/box 성격을 보존
  - DOCX horizontal merge 로 생기는 `접수방법 | 접수방법` 같은 중복 셀은 렌더 전 정규화
  - live evidence / regression anchors:
    - control DOCX: `300233_계약관계자변경.docx`
    - positive DOCX: `300138_라이프앱가능업무.docx`
  - 이 run 에서 확인된 문제 2개:
    - box section loss
    - horizontal merged header/value duplication

- artifact 저장 루트 조정
  - 기본 `/tmp/markbridge` 대신 workspace 내부 영속 경로를 우선 사용
  - current env: `MARKBRIDGE_WORK_DIR=/home/intak.kim/project/MarkBridge/.markbridge/runs`

- parser-policy 변경 시 회귀 검증 프로세스 추가
  - motivating 문서만 보지 않고 같은 파일 유형의 최근 run 을 control 로 함께 재파싱/비교
  - 최소 요구:
    - positive/negative unit test
    - motivating sample 재파싱
    - same-format recent control sample 재파싱
    - before/after artifact path 기록
  - 기준 문서: `docs/24-parsing-policy-and-tuning-guide.md`

## 지금 읽어야 할 문서

- 전체 처리 구조: [docs/16-processing-and-highlight-flow.md](/home/intak.kim/project/MarkBridge/docs/16-processing-and-highlight-flow.md)
- UI/API 계약: [docs/15-ui-api-contract.md](/home/intak.kim/project/MarkBridge/docs/15-ui-api-contract.md)
- downstream handoff: [docs/18-downstream-handoff-contract.md](/home/intak.kim/project/MarkBridge/docs/18-downstream-handoff-contract.md)
- benchmark / evaluation: [docs/19-repair-benchmark-and-evaluation.md](/home/intak.kim/project/MarkBridge/docs/19-repair-benchmark-and-evaluation.md)
- architecture overview: [docs/20-architecture-and-delivery-overview.md](/home/intak.kim/project/MarkBridge/docs/20-architecture-and-delivery-overview.md)

## 최근 핵심 파일

- parser / line mapping
  - [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
  - [src/markbridge/renderers/markdown.py](/home/intak.kim/project/MarkBridge/src/markbridge/renderers/markdown.py)
- validation / repair
  - [src/markbridge/validators/execution.py](/home/intak.kim/project/MarkBridge/src/markbridge/validators/execution.py)
  - [src/markbridge/repairs/formula.py](/home/intak.kim/project/MarkBridge/src/markbridge/repairs/formula.py)
  - [src/markbridge/pipeline/orchestrator.py](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)
- API surface
  - [src/markbridge/api/models.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/models.py)
  - [src/markbridge/api/service.py](/home/intak.kim/project/MarkBridge/src/markbridge/api/service.py)
- frontend
  - [frontend/src/App.tsx](/home/intak.kim/project/MarkBridge/frontend/src/App.tsx)
  - [frontend/src/types.ts](/home/intak.kim/project/MarkBridge/frontend/src/types.ts)
  - [frontend/src/index.css](/home/intak.kim/project/MarkBridge/frontend/src/index.css)

## 실제 확인된 상태

- sample PDF 기준 live API에서 `repair_candidates`가 생성됨
- sample count: `73`
- 예시:
  - `1.3. 해지율(      )` -> deterministic / llm candidate `q_{x+t}^{L}`
  - table row label `  ` -> deterministic / llm candidate `q_{x+t}^{L}`
  - formula placeholder -> `llm_required`
- approved sample CLI live run 기준
  - `repair_candidate_count=73`
  - `suggested_patch_count=31`
  - `recovered_deterministic_count=31`
  - `unresolved_repair_issue_count=42`
  - `unresolved_by_class=formula_placeholder=42`
  - `unresolved_by_reason=llm_not_requested=42`
  - `preferred_markdown_kind=resolved`
  - `policy=resolved_with_fallback`
  - `review_required=true`
  - `readiness_label=fragile`
- approved sample CLI live run with `--llm` 기준
  - LLM routing이 `pypdf` 를 선택
  - 초기 검증에서는 `repair_generated_candidates=0`, `repair_error=Unterminated string...` 가 관찰됨
  - prompt 압축 + repair output token budget 확장 후 재검증
  - `repair_candidate_count=10`
  - `llm_candidate_count=5`
  - `suggested_patch_count=2`
  - `recovered_deterministic_count=0`
  - `recovered_llm_count=2`
  - `unresolved_repair_issue_count=3`
  - `unresolved_by_class=inline_formula_corruption=3`
  - `unresolved_by_reason=llm_candidate_not_selected=3`
  - `llm_used=true`
  - `resolution_summary.issues[*].llm_attempted=true` 로 accounting fix 확인
  - `llm_diagnostics.repair_response_preview` 에서 candidate preview 확인 가능
  - 즉, 지금은 routing 뿐 아니라 repair candidate 생성도 실제로 동작함
  - 다만 generated 5개 중 final selected 는 2개라 ranking/policy 튜닝 여지는 남음
  - 현재는 issue별 winner / rejected candidate reason 까지 API와 UI에서 직접 확인 가능
  - 최신 live 재검증에서도 `repair_generated_candidates=5`, `resolved_issue_count=2`, `unresolved_repair_issue_count=3`
  - unresolved reason은 이제 `selected_patch_not_applied=3` 로 수렴
  - 즉, 병목은 생성 부족보다 patch anchoring/applicability 쪽으로 좁혀짐

## 다음 우선 작업

1. automatic LLM repair execution 확대
- `llm_recommended=true` 후보는 `llm_requested=true` run 에서 실제 LLM 처리 대상으로 보냄
  - 현재 임의 상한 `[:8]` 제거 완료
- deterministic 와 LLM 결과를 issue별로 랭크해서 최종 patch 선택
- 다음 live 검증은 `llm_requested=true` 기준으로 placeholder 해소율을 확인해야 함
- 특히 `llm_used=true` 인데 `llm_candidate_count=0` 인 케이스를 더 잘 설명해야 함
  - 현재는 `llm_diagnostics` 와 UI 에 attempted/generated/error/response_available/response_preview 를 노출
  - prompt 압축 + repair output token budget 확장으로 malformed JSON / truncation 문제는 완화됨
- generated candidate 중 어떤 것이 final patch 에 채택/기각되는지 ranking 근거를 API/UI에 노출 완료
- 현재 남은 병목은 selection policy 자체를 더 똑똑하게 조정하는 것
- 현재 selection fallback은 이미 들어가 있음
  - 상위 rank candidate가 apply 실패하면 다음 applicable candidate를 시도
  - 다음 단계는 LLM winner 자체의 `target_text` anchoring 품질을 높여 `selected_patch_not_applied` 를 줄이는 것
- routing은 이제 recommendation 즉시 override가 아니라 baseline vs recommendation probe 비교 후 선택
  - `routing_baseline_parser`
  - `routing_selected_parser`
  - `routing_override_applied`
  - `routing_comparison_preview`
- sample PDF live 검증에서 `pypdf` recommendation은 실제로 기각되고 `docling` baseline 유지 확인
  - `baseline=docling score=89.6`
  - `recommended=pypdf score=-4.74`
  - `heading_count 20 -> 0`
  - `average_line_length 29.92 -> 232.43`
- LLM repair는 이제 large target set을 batch로 분할 실행
  - retry split까지 넣은 latest live run on docling baseline:
  - `repair_attempted_issues=67`
  - `repair_generated_candidates=67`
  - `llm_candidate_count=67`
  - `suggested_patch_count=73`
  - `recovered_llm_count=67`
  - `unresolved_repair_issue_count=0`
  - `repair_error=null`
  - `readiness_label=reviewable`
  - `recommended_next_step=Use final resolved markdown for downstream and keep source markdown for audit.`
- UI layout 정리 반영
  - initial screen에서 `Parser hint` 높이를 `LLM assist`와 맞춤
  - `Markdown preview`와 `Validation review`가 같은 grid row에 오도록 정렬
  - preview line badge와 patch summary에서 `LLM patched` / `Deterministic patched` 구분 표시
- 실험용 first placeholder probe 추가
  - CLI: `python3 -m markbridge.cli probe-first-formula <run_dir> [--llm]`
  - `final_resolved.md`의 첫 `<!-- formula-not-decoded -->`를 찾고
  - 주변 markdown 문맥으로 page text match를 수행한 뒤
  - matched page 전체 이미지를 artifact로 저장하고
  - 선택적으로 multimodal LLM에 JSON patch object 형태로 probe 가능
- latest probe 결과
  - sample PDF first placeholder는 `final_resolved.md:71`
  - page match는 `page_number=2`, `score=0.8095`
  - whole-page image를 보낸 multimodal probe는 동작했지만 heading 오탐이 났음
  - region crop으로 좁힌 뒤에는 실제 formula-like reconstruction이 나오기 시작함
  - latest 좁은 crop 결과도 `apply_as_patch=false`, `confidence=0.36`
  - 즉 현재 상태는 `review object는 생성 가능`, `자동 markdown patch는 아직 unsafe`
- 중요한 현재 한계
  - `resolution_summary`상 resolved issue가 많아도 `final_resolved.md` 안에 `<!-- formula-not-decoded -->`가 남아 있을 수 있음
  - 즉 현재는 candidate/selection accounting과 markdown materialization이 완전히 같은 의미가 아님
  - placeholder 잔존 시 canonical downstream은 이제 `source`로 gate됨
  - 다만 UI highlight는 아직 미완
  - 지금 노란 highlight는 `이 줄은 원래 issue가 있었다` 정도의 의미로 남아 있어, `이미 해결됨`과 `아직 unresolved`를 분리하지 못함

2. unresolved accounting 정교화
- 현재는 issue별 unresolved reason / class / llm attempted 여부, winner candidate, selection reason, rejected reason 까지 저장 및 응답 반영됨
- 다음 단계는 selected winner가 실제 apply 실패한 케이스를 더 줄이도록 patch anchoring/policy 를 보강하는 것

3. UI 가독성 정리
- parser 선택 -> parsing -> issue -> deterministic repair -> llm repair -> final resolved -> downstream 흐름이 더 직접 보이게 수정
  - evaluation / preview 에는 반영됨
  - 다음은 trace/progress 영역에 stage별 recovery accounting 요약 추가
- `final resolved`의 노란 line 의미를 분리해야 함
  - `was_flagged_but_resolved`
  - `still_unresolved_in_final`
- `<!-- formula-not-decoded -->`가 남은 line은 별도 unresolved residue styling과 badge로 표시해야 함
- `llm patch` / `det patch` badge와 unresolved residue badge를 동시에 보여줄 수 있게 line-state model을 정리해야 함

4. unresolved `formula-not-decoded` residue 처리
- 현재 정책
  - placeholder가 남으면 canonical downstream은 `source`
  - `final resolved`는 review artifact로만 유지
  - first placeholder probe 결과는 `patch object first`로 남기고, `apply_as_patch=false`면 markdown에 반영하지 않음
- 다음 결정 필요
  - first placeholder만 probe할지, 모든 residue에 probe sidecar를 만들지
  - downstream contract를 `canonical markdown + residual unresolved objects`로 확장할지
  - residue object를 별도 artifact로 저장할지, `resolution_summary`에 흡수할지

5. benchmark 샘플셋 축적
- 실제 업무 문서에서 anonymized repair case를 모아 `docs/19` 기준으로 benchmark set 구성

## 병렬 작업 트랙

### Track A. Resolution Engine
- final resolved markdown assembly
- patch ranking policy
- unresolved issue accounting

### Track B. LLM Recovery Execution
- llm escalation coverage 정리
- placeholder / structure-loss 우선 처리
- mixed deterministic + llm repair run 검증

### Track C. UI / Monitoring
- 현재 downstream 으로 실제 나갈 markdown 명시
- 단계별 처리 현황 가시화
- unresolved vs recovered issue 구분
- `final resolved`의 노란 line 의미를 `과거 issue 이력`과 `현재 unresolved residue`로 분리
- `formula-not-decoded` residue와 formula probe 결과를 operator가 한눈에 읽을 수 있게 표시

### Track D. Benchmark / Docs
- repair benchmark 축적
- handoff / architecture / operator docs 갱신

## 검증 커맨드

- backend tests:
  - `pytest -q tests/unit/test_formula_repairs.py tests/unit/test_markdown_renderer.py tests/unit/test_validators_execution.py tests/unit/test_api_app.py tests/unit/test_storage.py`
- frontend build:
  - `cd frontend && npm run build`

## 서버 상태

- live backend는 `http://localhost:8000` 에서 재시작된 최신 코드 기준이어야 함
- 프런트에서 이상하면 강새로고침 후 다시 parse 해볼 것
