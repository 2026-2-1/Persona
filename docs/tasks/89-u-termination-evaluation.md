# #89 U 탐색 종료와 사후 독립 평가

2026-10-20 대시보드 후속: 공개 사이트라는 이유로 모든 evaluator_id를 unverified-external-site로 바꾸던 동작을 수정했다. 명시한 프로필은 같은 사이트·같은 과업일 때 보존하고, 기본 대시보드는 등록된 데카트론 ‘8만원 이하 러닝화 상세 확인’과 사이트/과업이 일치할 때만 기존 부분 프로필을 연결한다. 다른 목표 가격·사이트에는 오적용하지 않는다. 알려진 홈페이지/검색 URL에 상세 이름·가격이 모두 없으면 미도달로 판정하고, 상세 화면의 모호한 DOM은 기존 unknown을 유지한다. 이 설정은 종료 후 독립 평가 전용이고 모델 입력에 넣지 않는다.

## 목표와 확정 범위

AI의 `terminate`는 브라우저 탐색 종료 신호다. 성공·실패는 종료 이후 현재 최종 화면을 별도 evaluator가 판정한다. 실행 중 evaluator 결과로 AI를 조기 종료하지 않는다. 사용자가 정한 GPU Qwen + 실제 Decathlon 방향을 유지하며, 현재 공개 과업 설정의 러닝화 검색 결과 시작점과 상품명에 `러닝화` 포함·가격 80,000원 이하의 상세 검사를 그대로 사용한다. 색상·사이즈·재고·픽업 등 프로필 밖 조건은 추가하지 않는다.

## 변경 전 → 변경 후

| 변경 전 | 변경 후 |
|---|---|
| 각 행동 뒤 evaluator를 호출하고 `success`면 `verified_success`로 즉시 종료 | 행동 중 evaluator를 호출하지 않고 모델 종료·자원 한도·중지를 기다린 뒤 한 번 평가 |
| 반복 fingerprint/action 횟수 초과로 `stuck` 조기 종료 | 해당 조기 종료 제거; `max_steps`, run timeout, model/browser error, 사용자 중지는 유지 |
| 종료 선언 단계의 관찰을 그대로 평가 | Slow/Brain 종료 → 새 최종 관찰 저장 → 동일 활성 브라우저 화면을 평가 → 브라우저 종료 |
| 평가 결과와 종료 사유가 묶임 | `termination_reason`과 독립 `verification`을 분리 저장 |

## 실행·기록 계약

1. `decision.action is None`인 U `terminate`를 `agent_finished`로 기록한다. legacy `give_up` 종료도 유지한다. 종료 선언 자체는 성공 판정이 아니다.
2. 행동 뒤 관찰은 다음 모델 판단을 위한 기록이며 evaluator를 호출하지 않는다. 각 step의 `verification`은 `unknown`, reason은 `deferred_until_run_end`다. 과거 step을 사후 성공으로 덮어쓰지 않는다.
3. 어떤 정상 종료·자원 제한·모델 오류·취소로 loop가 끝나도 가능한 경우 Brain/Slow를 먼저 닫고 활성 탭의 최종 관찰 JSON/PNG를 저장한 후 독립 evaluator를 한 번 호출한다. evaluator 입력에 평가 결과를 모델로 되돌려 보내지 않는다.
4. `final_evaluation.json`은 termination reason, 마지막 termination step ID, 최종 observation ID/URL/시각, evaluator 결과를 연결한다. `summary.json`은 독립 `verification`, evaluator와 최종 observation 필드를 보유한다. 실행/비교 기록에 같은 필드를 전달한다.
5. 최종 캡처 실패·evaluator 예외·유효 화면 부재는 `unknown` 및 구체 reason으로 남긴다. 이전 관찰을 최종 관찰인 것처럼 사용하지 않는다. 원래 model/browser/cancel/timeout 종료 사유는 그대로 보존한다. 종료 뒤 판정은 추가 행동을 시작하지 않는다.
6. `max_steps`, run timeout, budget exhaustion, cancellation은 task completion과 별도로 남는다. 마지막 화면이 검증 기준을 만족하면 `verification=success`일 수 있으며 종료 사유는 바뀌지 않는다. 시스템 오류와 평가 결과도 별도 필드다.
7. 현재 `configs/study-decathlon-live.json`의 제한적 공개 프로필(`detail_basic`: 상품명·가격)을 재사용한다. evaluator 정답은 모델 prompt에 넣지 않는다. 시작 URL 제출, 색상/사이즈/재고/픽업 성공으로 확대하지 않는다.

## 원본과 로컬 차이

2026-10-19 취소 후속: `asyncio.CancelledError`도 종료 원인 `cancelled`로 남긴다. 탐색 중 취소는 브라우저를 열어 둔 상태에서 Brain/Slow를 정리하고 새 최종 화면을 평가한다. 브라우저 진입·최종 캡처·정리 도중 취소로 화면을 얻지 못하면 `unknown/cancelled_before_final_observation`을 기록한다. 브라우저 종료 도중 취소되어도 최종 JSON과 summary의 종료 사유를 일치시킨다. 모든 writer를 닫은 뒤 원래 취소를 다시 전파하므로 CLI/상위 비교 실행의 취소 의미는 유지한다.

- [U terminate action 처리](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/env.py#L1005-L1021)
- [U 종료 관찰에서 terminated/score 처리](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/env.py#L1199-L1213)
- [U batch에서 eval 생략](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/experiment.py#L39-L45)
- 로컬은 U의 미구현 `evaluate_task()` 대신 독립적인 Decathlon evaluator를 종료 뒤 호출한다. `termination_reason`, error provenance, Qwen/예산 기록은 로컬 run 계약으로 보존한다.

## 검증

회귀는 중간 화면 success 뒤에도 AI가 종료 선언까지 계속하는지, evaluator가 Slow close/최종 capture 뒤 한 번만 실행되는지, terminate·max_steps·timeout·cancel·model/browser error의 종료 사유가 판정과 독립적인지 검사한다. 최종 캡처 실패는 stale 화면을 평가하지 않고 unknown으로 남긴다. 실행/비교 summary와 지표가 최종 verification을 사용한다.

실제 GPU Qwen/Decathlon 실행은 로컬 fake-provider 검사와 구분해 verification에 기록한다. 사용자 개인 세션·비밀 설정·runs 원자료는 저장소에 추가하지 않는다.

## 구현 결과

- 회귀는 구현 전에 실패를 재현했다. 중간 evaluator success가 첫 행동 뒤 탐색을 멈추고, 사후 `final_evaluation.json`이 없는 상태였다.
- 관련 runner/Decathlon/evaluator/memory/comparison/usage/metrics/core 집중 검사 73개가 통과했다. 최종 capture/evaluator 실패와 비교 provenance를 추가한 뒤 17개 집중 검사도 통과했다.
- 전체 pytest는 529 passed, 1 failed였다. 남은 테스트는 예산 종료라면 verification도 반드시 unknown이어야 한다고 가정했다. 사용자 계약에 맞춰 마지막 화면 판정 failure를 확인하도록 수정하고 해당 테스트를 별도로 다시 실행해 통과시켰다. 전체를 수정 후 다시 한 번 실행하지 않았으며 최종 원격 CI 결과를 확인한다.
- 최종 shutdown/capture/evaluator 및 비교 provenance 경로 집중 재검사는 **10 passed in 16.06s**였다.
- Qwen GPU와 공개 Decathlon은 이번 변경 검증에서 호출하지 않았다. 공개 URL·상품 상태의 실제 현재 응답과 Qwen 종료 행동 품질은 미검증이다.

고정 이슈: [#89](https://github.com/2026-2-1/Persona/issues/89). 선행은 [#88 PR #97](https://github.com/2026-2-1/Persona/pull/97), [#87 PR #96](https://github.com/2026-2-1/Persona/pull/96), [Qwen PR #91](https://github.com/2026-2-1/Persona/pull/91)이다. U 전체 전환은 #90 검증 후속까지 완료되어야 한다.

2026-10-20 실제 후속: 공개 detail_price에 함께 구매 합계가 섞여unknown이 되는 것을 재현하고 #product-summary-container로 범위를 좁혔다. 상품 내부 가격 충돌/가격 부재는unknown을 유지한다. 원래 자율run의unknown을 덮어쓰지 않고 동일 실제 페이지의 별도 재검사에서 상품명/79,900원success를 확인했다. 상세 검증 이력을 따른다.
