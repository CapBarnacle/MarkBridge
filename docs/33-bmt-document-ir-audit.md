# 33. BMT DocumentIR Audit Snapshot

이 문서는 `s3://rag-580075786326-ap-northeast-2/bmt/` 샘플을 기준으로 실행한 `DocumentIR` chunking readiness audit의 첫 결과를 정리한 것이다.

실행 산출물 위치:

- [`.markbridge/audits/document-ir/2026-04-23-bmt/`](/home/intak.kim/project/MarkBridge/.markbridge/audits/document-ir/2026-04-23-bmt)

샘플별 raw artifact:

- 각 샘플 디렉터리 안의 `audit-summary.json`
- 각 샘플 디렉터리 안의 `document-ir.json`

## 1. 사용 샘플

| 포맷 | 샘플 |
|---|---|
| PDF | `산출방법서_신한큐브종합건강상해보험(무배당, 해약환급금 미지급형)_230404_v2.pdf` |
| PDF | `000.주계약약관_(355간편)신한통합건강보장보험원(ONE)(무배당, 해약환급금 미지급형)_20240101_v0.2.pdf` |
| DOCX | `300138_라이프앱가능업무.docx` |
| DOCX | `300233_계약관계자변경.docx` |
| XLSX | `건강보험진료통계-다빈도상병별현황_2022.xlsx` |
| DOC | `(무)종신보험표준형_20210101_산출방법서.doc` |

참고:

- 이번 샘플셋에는 HWP가 없었다.

## 2. 요약 표

| 샘플 | format | parser | blocks | issues | handoff | block source | heading level | table header depth | table title | table caption | table page range |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `000.주계약약관...v0.2.pdf` | `pdf` | `docling` | 464 | 0 | `accept` | 0.0 | 1.0 | 1.0 | 1.0 | 0.3333 | 0.0 |
| `산출방법서_신한큐브...v2.pdf` | `pdf` | `docling` | 203 | 103 | `degraded_accept` | 0.0 | 1.0 | 1.0 | 1.0 | 0.6667 | 0.0 |
| `300138_라이프앱가능업무.docx` | `docx` | `python-docx` | 26 | 0 | `accept` | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| `300233_계약관계자변경.docx` | `docx` | `python-docx` | 64 | 0 | `accept` | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| `건강보험진료통계-다빈도상병별현황_2022.xlsx` | `xlsx` | `openpyxl` | 2 | 0 | `accept` | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| `(무)종신보험표준형_20210101_산출방법서.doc` | `doc` | `libreoffice` | 131 | 1 | `degraded_accept` | 0.0 | 1.0 | 1.0 | 1.0 | 0.8 | 0.0 |

관찰 포인트:

- `parser_block_ref`는 전 샘플에서 100% 채워졌다.
- `heading_level`은 heading block 기준 전 샘플에서 100% 채워졌다.
- `table_header_depth`와 `table_title`도 이번 샘플에서는 전부 채워졌다.
- `table_caption`은 DOCX에서는 잘 채워졌지만 PDF/DOC/XLSX는 편차가 남아 있다.
- `table_page_range`는 전 샘플에서 0.0이었다.
- block-level `source` coverage는 XLSX를 제외하면 모두 0.0이었다.

## 3. 포맷별 해석

### PDF / `docling`

- heading, list, table 구조는 chunking input으로 쓸 수 있을 정도로 유지된다.
- `parser_block_ref`, `heading_level`, `table_header_depth`, `table_title`은 충분히 채워진다.
- 그러나 block-level page/source span은 전혀 채워지지 않았다.
- 따라서 citation, page-aware chunk merge/split, retrieval evidence에는 아직 약하다.

실무 판단:

- PDF는 현재도 section-aware chunking의 초안 입력으로는 쓸 수 있다.
- 다만 page trace가 없어서 retrieval citation 품질을 높이려면 추가 보강이 필요하다.

### DOCX / `python-docx`

- heading/table 구조는 충분히 좋다.
- table title/caption도 현재는 preceding heading 기반으로 안정적으로 채워진다.
- layout box가 `note`로 남는 것도 chunking에 유리하다.
- 반면 block-level source span은 전혀 없다.

실무 판단:

- DOCX는 chunking 구조 입력 측면에서는 현재 가장 실용적이다.
- 다음 보강 우선순위는 source span보다 section path와 table grouping policy 설계 쪽에 더 가깝다.

### XLSX / `openpyxl`

- 이번 샘플에서는 block-level `source` coverage가 1.0이었다.
- heading은 sheet 이름, table은 sheet와 row range를 보존한다.
- chunk provenance 관점에서는 현재 포맷 중 가장 준비가 잘 되어 있다.
- 다만 table caption과 page-range류 정보는 구조상 비어 있다.

실무 판단:

- XLSX는 `DocumentIR -> ChunkSourceDocument` 변환의 기준 포맷으로 삼기 좋다.
- 이후 보강 포인트는 cell address, number format, formula metadata 쪽이다.

### DOC / `libreoffice`

- 구조 자체는 DOCX route를 재사용하므로 heading/table 정보는 usable하다.
- 그러나 source span은 없다.
- 이번 샘플은 validation issue 1건으로 `degraded_accept`였다.

실무 판단:

- DOC는 chunking input으로는 사용 가능하지만 신뢰도 metadata를 같이 가져가야 한다.
- route kind, handoff decision, validation issue join이 중요하다.

## 4. 이번 audit로 확정된 우선순위

### 바로 다음 단계

| 우선순위 | 작업 | 이유 |
|---|---|---|
| 1 | `DocumentIR -> ChunkSourceDocument` 모델 설계 | DOCX/PDF/XLSX 모두 구조 chunking은 시작 가능한 수준 |
| 2 | validation issue와 block/chunk join 규칙 정의 | DOC/PDF degraded case를 chunk metadata로 반영해야 함 |
| 3 | DOCX/PDF source span 보강 후보 설계 | citation과 retrieval evidence 품질 향상에 필요 |

### 아직 미루어도 되는 것

| 작업 | 이유 |
|---|---|
| footnote/endnote IR | 이번 샘플셋에서는 우선순위가 높게 드러나지 않음 |
| image/footer block 적극화 | 현재 chunking 핵심 경로와 직접 연결되지 않음 |
| multi-page table page range 복원 | 필요하지만 `ChunkSourceDocument` 설계보다 선행할 정도는 아님 |

## 5. 현재 결론

현재 `DocumentIR`는 "chunking 설계를 시작하고 초기 구현을 붙일 수 있는 수준"에는 도달했다.

다만 아래는 아직 부족하다.

- PDF/DOCX/DOC의 block-level source span
- table page range
- validation issue와 chunk 품질 플래그 join

따라서 다음 작업은 parsing 보강을 더 오래 붙드는 것이 아니라, 지금 상태의 `DocumentIR`를 기준으로 `ChunkSourceDocument` handoff 모델을 설계하고, 필요한 부족 필드를 그 과정에서 다시 좁혀가는 것이 맞다.
