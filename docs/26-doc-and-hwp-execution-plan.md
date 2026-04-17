# DOC and HWP Execution Plan

이 문서는 `.doc` 와 `.hwp` 지원을 실제 작업 단위로 착수하기 위한 실행 계획이다.

핵심 전제:

- `.doc` 와 `.hwp` 는 같은 종류의 작업이 아니다.
- `.doc` 는 이미 변환 기반 실행 scaffold 가 있으므로 "활성화/검증" 작업에 가깝다.
- `.hwp` 는 아직 실행 경로 자체가 없으므로 "전략 결정 + 신규 구현" 작업이다.

## Current State

### DOC

- intake/API surface는 이미 열려 있다.
- inspection은 `libreoffice` 와 `antiword` readiness를 함께 본다.
- runtime routing은 `DocumentFormat.DOC -> libreoffice -> antiword` 순서의 scaffold를 이미 가진다.
- parser 구현은 `.doc -> .docx` 변환 뒤 기존 DOCX parser를 재사용한다.
- `antiword` 가 설치된 환경에서는 text fallback route도 바로 활성화될 수 있다.
- `antiword` fallback이 선택되면 handoff는 강제로 `degraded_accept` 로 표기되고 route kind가 metadata/notes에 남는다.
- 현재 병목은 기능 부재보다:
  - target runtime에서 LibreOffice가 실제로 설치되어 있는지,
  - `antiword` fallback을 운영상 허용할지,
  - 변환 결과 품질이 운영상 수용 가능한지,
  - 실패/trace/artifact가 충분히 설명적인지
  에 가깝다.

### HWP

- intake/API surface는 이미 열려 있다.
- inspection은 `hwp5txt` readiness를 볼 수 있다.
- runtime routing에는 `hwp5txt` text route scaffold가 추가되어 있다.
- `hwp5txt` text route가 선택되면 handoff는 강제로 `degraded_accept` 로 표기되고 route kind가 metadata/notes에 남는다.
- 다만 current runtime에는 command가 없어서 실제 실행은 여전히 explicit `hold` 상태다.
- 즉 `.hwp` 는 완전한 공백에서 "tool-activated text route scaffold" 단계로 진전된 상태다.

## Goal Split

### Track A. DOC Operational Enablement

목표:

- `.doc` 입력이 실제 target runtime에서 end-to-end parse/export/API 경로를 통과하게 한다.
- 실패 시에는 운영자가 이유를 trace와 notes에서 명확히 알 수 있게 한다.

완료 정의:

- sample `.doc` 입력이 upload/S3 경로 모두에서 실행 가능
- routing이 `libreoffice` 를 선택
- 변환 후 DOCX parser 결과가 markdown/export/API까지 정상 연결
- 실패 케이스는 명확한 message/warning/artifact를 남김
- regression test와 최근 run evidence가 남아 있음

### Track B. HWP Route Decision

목표:

- `.hwp` 를 어떤 executable route로 처리할지 먼저 결정한다.

후보 방향:

1. 변환 기반
   - `hwp -> docx`
   - `hwp -> pdf`
   - `hwp -> hwpx`
2. 전용 parser 라이브러리 기반
3. 외부 서비스/도구 기반

완료 정의:

- target environment에서 실행 가능한 후보 1개 이상 식별
- licensing / packaging / installability / fidelity tradeoff 정리
- chosen route 또는 explicit defer decision 기록

### Track C. HWP MVP Implementation

목표:

- chosen route를 통해 최소한 paragraph / heading / table 수준의 shared IR을 생성한다.

완료 정의:

- `.hwp` upload/S3 parse가 `hold` 가 아닌 executable path로 진입
- 최소 markdown/export/API 응답이 생성
- validator/repair/downstream handoff가 깨지지 않음
- known limitation이 docs와 notes에 남음

## Work Breakdown

## A1. DOC runtime validation

작업:

1. target runtime에서 `libreoffice` / `soffice` availability 확인
2. `GET /v1/runtime-status` 에서 `libreoffice.enabled=true` 확인
3. sample `.doc` 1개 이상 확보
4. CLI 또는 API로 실제 parse 실행
5. 변환 성공/실패 로그와 artifact 위치 기록

확인 포인트:

- routing selected parser
- conversion stderr/stdout
- converted `.docx` 생성 여부
- final canonical markdown 생성 여부

권장 명령:

```bash
python3 -m markbridge.cli runtime-status
```

```bash
curl -sS http://127.0.0.1:8000/v1/runtime-status
```

## A2. DOC failure-mode hardening

작업:

1. 변환 실패 시 API notes/trace/message가 충분한지 확인
2. 필요한 경우 conversion artifact path와 raw failure message 노출 보강
3. parse decision이 `hold` / `failed` 로 가야 하는 기준 정리

완료 기준:

- 운영자가 "왜 `.doc` 가 안 됐는지" 코드를 보지 않고 알 수 있음

## A3. DOC quality validation

작업:

1. motivating `.doc` sample 재파싱
2. converted `.docx` 결과가 기존 DOCX heuristics와 잘 맞는지 확인
3. same-format control sample 1개 이상과 비교
4. artifact path, structural delta, residual issue를 문서에 기록

특히 볼 것:

- heading survival
- table fidelity
- merged-cell duplication
- layout box loss

## A4. DOC test coverage

필수 테스트:

1. `libreoffice` unavailable 시 explicit failure/hold behavior
2. `libreoffice` available 시 route selection
3. conversion success path smoke test
4. export API까지 canonical markdown exposure 확인

대상 파일:

- `tests/unit/test_pipeline.py`
- `tests/unit/test_api_service.py`
- 필요 시 `tests/unit/test_api_app.py`

## B1. HWP route survey

작업:

1. target environment에서 설치 가능한 후보 조사
2. Python binding / CLI tool / conversion chain 후보 정리
3. 아래 항목 비교:
   - install complexity
   - Linux compatibility
   - table fidelity
   - heading preservation
   - batch execution suitability
   - on-prem viability

산출물:

- short decision note or decision log entry

## B2. HWP execution decision

작업:

1. 후보 1개 선택
2. fallback strategy 정리
3. unsupported feature policy 정리

결정 시 반드시 남길 것:

- 왜 이 경로를 선택했는지
- 어떤 fidelity limitations를 수용하는지
- 어떤 운영 조건에서만 활성화되는지

## C1. HWP inspection and runtime integration

작업:

1. inspection에 chosen route readiness 반영
2. runtime status에 HWP parser/tool status 반영
3. executable candidate set에 HWP route 추가

완료 기준:

- `runtime-status` 에서 HWP 경로 availability가 보임
- routing이 unsupported 대신 executable candidate를 가질 수 있음

## C2. HWP parser wrapper implementation

작업:

1. chosen route 호출 래퍼 추가
2. output을 shared IR로 매핑
3. minimum block kinds:
   - `heading`
   - `paragraph`
   - `table`
   - 필요 시 `note`

대상 파일 후보:

- `src/markbridge/parsers/basic.py`
- 필요 시 `src/markbridge/parsers/hwp.py` 신규 분리
- `src/markbridge/parsers/__init__.py`

## C3. HWP downstream compatibility

작업:

1. markdown renderer 결과 확인
2. validator 과민 탐지 여부 확인
3. repair 단계가 HWP output에서도 안전한지 확인
4. export/content/block API까지 확인

완료 기준:

- parse response
- canonical markdown export
- block export
- downstream handoff
가 모두 깨지지 않음

## C4. HWP test coverage

필수 테스트:

1. route unavailable 시 explicit hold
2. route available 시 executable candidate 노출
3. parser wrapper smoke test
4. API response/export smoke test

## Recommended Order

1. A1
2. A2
3. A3
4. A4
5. B1
6. B2
7. C1
8. C2
9. C3
10. C4

## Immediate Next Actions

가장 먼저 할 일:

1. target runtime에서 `libreoffice` 실제 availability 확인
2. sample `.doc` 로 end-to-end parse 실행
3. `.doc` 에서 실제 막히는 지점이 환경인지 품질인지 trace로 분리
4. 그 결과를 기준으로 DOC 활성화 backlog를 확정
5. 동시에 HWP route survey 후보를 짧게 정리

## Key Code References

- DOC conversion helper:
  - [src/markbridge/parsers/conversion.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/conversion.py)
- parser runtime dispatch:
  - [src/markbridge/parsers/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
- runtime route availability:
  - [src/markbridge/routing/runtime.py](/home/intak.kim/project/MarkBridge/src/markbridge/routing/runtime.py)
- inspection:
  - [src/markbridge/inspection/basic.py](/home/intak.kim/project/MarkBridge/src/markbridge/inspection/basic.py)
- current policy context:
  - [docs/22-chunk-boundary-and-format-expansion.md](/home/intak.kim/project/MarkBridge/docs/22-chunk-boundary-and-format-expansion.md)
  - [docs/24-parsing-policy-and-tuning-guide.md](/home/intak.kim/project/MarkBridge/docs/24-parsing-policy-and-tuning-guide.md)
