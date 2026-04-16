# Resume Brief

이 문서는 다음 작업 세션에서 즉시 재개할 수 있도록 현재 상태와 우선 작업 지점을 압축 정리한다.

## Current Confirmed State
- 설계 기준 문서는 `docs/01-architecture-spec.md`, `docs/04-decision-log.md`, `docs/08-session-history.md` 이다.
- 현재 제품 경계는 RAG 전체가 아니라 parsing layer 이다.
- OCR 은 MVP 범위 밖이며, `docling` PDF 경로도 OCR disabled 로 동작해야 한다.
- 라우팅은 project policy 와 runtime availability 를 동시에 만족하는 후보만 사용한다.
- trace 는 내부 로그가 아니라 사용자에게 노출 가능한 product artifact 로 취급한다.
- validator 가 canonical issue record 의 source of truth 이고, quality gate 는 `accept`, `degraded_accept`, `hold` 를 사용한다.

## Code Snapshot
- PDF active route: `docling` first, `pypdf` fallback
- DOCX active route: `python-docx`
- XLSX active route: `openpyxl`
- DOC route: LibreOffice conversion scaffold exists, runtime activation still blocked by system tooling
- HWP: intake 허용, 실행은 explicit `hold`
- API, CLI, pipeline, exporter, validator, tracing 기본 경로가 이미 구현되어 있다
- 전체 테스트: `17 passed`

## Verified Restart Target
- 가장 자연스러운 다음 작업은 `docling` Markdown 기반 표 정규화 개선이다.
- 현재 병목은 파이프라인의 별도 normalize 모듈이 아니라 [`src/markbridge/parsers/basic.py`](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py) 내부 `_blocks_from_markdown()` 이다.
- 이 함수가 Markdown 표를 단순 split 하면서 보험 PDF 의 복잡한 표에서 warning 을 과다 발생시킬 가능성이 크다.

## Files To Reopen First
- [`docs/08-session-history.md`](/home/intak.kim/project/MarkBridge/docs/08-session-history.md)
- [`src/markbridge/parsers/basic.py`](/home/intak.kim/project/MarkBridge/src/markbridge/parsers/basic.py)
- [`src/markbridge/pipeline/orchestrator.py`](/home/intak.kim/project/MarkBridge/src/markbridge/pipeline/orchestrator.py)
- [`src/markbridge/validators/rules.py`](/home/intak.kim/project/MarkBridge/src/markbridge/validators/rules.py)
- [`tests/unit/test_pipeline.py`](/home/intak.kim/project/MarkBridge/tests/unit/test_pipeline.py)

## Practical Next Steps
1. `docling` PDF 샘플에서 어떤 표 패턴이 현재 validator warning 으로 이어지는지 재현한다.
2. `_blocks_from_markdown()` 의 표 인식 규칙을 조정해 separator row, ragged row, multiline content 처리를 더 보수적으로 만든다.
3. 필요한 경우 parser 단계와 validator 단계의 책임을 다시 나눠, parser 는 구조를 덜 공격적으로 확정하고 validator 는 이상 징후를 더 정확히 분류한다.
4. 보험 PDF 회귀 테스트를 추가해 warning volume 과 handoff decision 이 안정적으로 유지되는지 확인한다.

## Useful Commands
```bash
pytest -q
```

```bash
python -m markbridge.cli runtime-status
```

```bash
python -m markbridge.cli parse-file <local-path>
```
