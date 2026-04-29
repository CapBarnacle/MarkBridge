# 45. Retrieval Q&A Searchability Check

이 문서는 현재 가지고 있는 질문-답변 세트가 검색에서 얼마나 잘 잡히는지 확인한 결과를 정리한 것이다.

기준 데이터는 retrieval subset 6건이며, 현재 저장된 평가 산출물을 그대로 사용했다.

- 질문/정답 원본: [`.markbridge/evals/retrieval-subset/answer_subset.jsonl`](/home/intak.kim/project/MarkBridge/.markbridge/evals/retrieval-subset/answer_subset.jsonl)
- weak baseline 평가: [`.markbridge/evals/retrieval-subset/weak_eval_baseline.json`](/home/intak.kim/project/MarkBridge/.markbridge/evals/retrieval-subset/weak_eval_baseline.json)
- dense rerank 평가: [`.markbridge/evals/retrieval-subset/dense_eval_small_rerank.json`](/home/intak.kim/project/MarkBridge/.markbridge/evals/retrieval-subset/dense_eval_small_rerank.json)

## 1. 평가 기준

- `top-1 exact`: 질문의 정답 문서가 검색 결과 1순위에 있는지
- `top-5 acceptable`: 질문의 정답 문서가 상위 5개 안에 있는지
- `acceptable docs`: 정답 텍스트에 명시된 문서명 전체

주의:

- `VOC 접수시 유의사항 알려줘.`는 정답 텍스트에 문서명이 2개(`OR`)로 적혀 있다.
- 이 경우 둘 중 하나만 top-1에 들어도 정답으로 본다.

## 2. 전체 요약

| config | collection / path | top-1 exact | top-5 acceptable | 해석 |
|---|---|---:|---:|---|
| weak baseline | same retrieval records, rule-based scoring baseline | 5 / 6 | 6 / 6 | 6개 중 1개는 top-1에서 틀렸지만, 상위 5개 안에는 정답이 들어왔다 |
| dense small rerank | `retrieval_subset_small_rerank` / `.markbridge/qdrant-dense-small-rerank` | 6 / 6 | 6 / 6 | 현재 기준에서는 질문 6건 모두 top-1에서 정답 문서가 잡혔다 |

## 3. 질문별 결과

| record_id | 질문 | 정답 문서 | weak baseline top-1 | dense rerank top-1 | 판정 |
|---:|---|---|---|---|---|
| 54 | 신한 SOL라이프 앱에서 한도증액 하는 방법 알려줘. | `300138_라이프앱가능업무.docx` | `300138_라이프앱가능업무.docx` / `1. 신한 SOL라이프 앱 이용방법` | `300138_라이프앱가능업무.docx` / `1. 신한 SOL라이프 앱 이용방법` | pass |
| 55 | 신한 SOL라이프 앱에서 제지급시 금액별 인증 방법 알려줘. | `300138_라이프앱가능업무.docx` | `300138_라이프앱가능업무.docx` / `1. 신한 SOL라이프 앱 이용방법` | `300138_라이프앱가능업무.docx` / `1. 신한 SOL라이프 앱 이용방법` | pass |
| 56 | 계약자 사망 시 계약자 변경 하는 방법 알려줘. | `300233_계약관계자변경.docx` | `300233_계약관계자변경.docx` / `4. 계약자 변경 _ 사망승계` | `300233_계약관계자변경.docx` / `4. 계약자 변경 _ 사망승계` | pass |
| 57 | 계약자 변경으로 내방할 경우 지참 해야 할 서류 알려줘. | `300233_계약관계자변경.docx` | `300233_계약관계자변경.docx` / `4. 계약자 변경 _ 사망승계` | `300233_계약관계자변경.docx` / `3) 계약자 변경 구비서류` | pass |
| 61 | 청약철회 가능기간 알려줘. | `300060_고객센터 청약철회 업무처리기준.docx` | `300060_고객센터 청약철회 업무처리기준.docx` / `1. 고객센터 청약철회 접수 및 지급기준` | `300060_고객센터 청약철회 업무처리기준.docx` / `1. 고객센터 청약철회 접수 및 지급기준` | pass |
| 63 | VOC 접수시 유의사항 알려줘. | `300155_고객센터 FC변경 접수방법.docx` 또는 `300060_고객센터 청약철회 업무처리기준.docx` | `300233_계약관계자변경.docx` / `1) 수익자 변경 유의사항 및 공통사항` | `300060_고객센터 청약철회 업무처리기준.docx` / `3. 계약자 미성년자인 경우 청약철회 기준` | pass |

## 4. 해석

- 현재 retrieval subset에서는 6건 모두 정답 문서가 top-5 안에 들어온다.
- baseline scoring에서는 6건 중 1건이 top-1에서 빗나갔다.
- dense rerank 조합에서는 6건 모두 top-1이 정답 문서로 맞았다.
- 가장 의미 있는 개선은 `VOC 접수시 유의사항 알려줘.` 케이스다.
  - baseline은 계약자 변경 문서로 치우쳤다.
  - dense rerank는 허용 가능한 정답 문서인 `300060_고객센터 청약철회 업무처리기준.docx`를 top-1로 올렸다.

## 5. 참고

이 결과는 전체 코퍼스가 아니라 현재 저장된 retrieval subset 기준이다.
전체 corpus reindexing 후에는 같은 형식으로 다시 비교하는 것이 맞다.
