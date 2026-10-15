# 계획 검토 6건 폐기 원인 진단

2026-10-16, `codex/latest-pr-integration-20261015` / 통합 PR #81 기준. 무료 로컬 Mock 실행을 진단한 결과이며, 실제 LLM이나 사람 행동에 대한 실험 결과가 아니다. 생산 코드와 실행 정책은 변경하지 않았다.

## 결론

계획 검토가 생성에 실패한 것이 아니다. **현재 runner는 계획 검토를 비동기 대기열에 넣은 직후, worker가 실행될 기회를 주기 전에 해당 검토를 받아들일 수 있는 유일한 decision 경계를 지난다.** 검토가 뒤늦게 완료되어도 다음 관찰 경계에서는 같은 observation·plan·version 조건이 맞지 않아 폐기된다. 마지막 검토는 다음 경계 없이 실행이 끝나 미소비로 폐기된다.

원본 실행 `20261015T145603-83f78314`의 검토 6건은 모두 `scheduled → started → completed → discarded`다. 앞의 5건은 `stale_context`, 마지막 1건은 `run_finished_unconsumed`다. 6건 모두 같은 관찰·계획의 Fast decision 시작보다 검토 시작이 늦었다. 따라서 이 0/6을 Slow 정책의 효과나 Novelty 근거로 사용하면 안 된다. 먼저 현재 runner의 결정 경계에 검토 결과가 도달할 기회를 확보하고, **실제 decision 입력 도달을 검증하는 회귀를 갖춘 뒤** 정책 실험을 진행해야 한다.

## 코드에서 확인한 순서

1. [runner.py 282–285행](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/runner.py#L282-L285)은 `schedule_plan_review()` 다음에 `begin_stage("decision")`을 호출한다. 두 호출 사이에 `await`가 없다.
2. [SlowLoop 예약 56–72행](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/slow_loop.py#L56-L72)은 대기열에 넣고 필요하면 `asyncio.create_task()`로 worker를 예약한 뒤 즉시 반환한다. 실행 중인 runner가 제어를 넘기기 전에는 새 작업이 시작될 수 없다. 기존 worker도 같은 이벤트 루프에서 진행된다.
3. [Brain의 소비 조건 132–158행](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/brain.py#L132-L158)은 **완료된 결과만** 가져온다. 계획 검토는 `decision`이며 observation ID·plan ID·version이 모두 같아야 채택된다. 한 번 지나간 해당 경계에서는 다시 확인하지 않는다. 뒤의 embedding 검색이 `await`하더라도 경계 검사는 이미 끝난 상태다.
4. 다음 단계의 `perception`은 새 observation으로 시작한다. 이때 완료 결과를 꺼내면서 검토를 `stale_context`로 폐기한다. [종료 처리 103–108행](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/brain.py#L103-L108)은 남은 완료 결과를 `run_finished_unconsumed`로 기록한다.

이 보호 조건은 오래된 계획·화면의 조언을 새 행동에 무조건 적용하지 않게 한다. 문제는 보호 조건 자체보다 **현재 호출 순서가 그 조건을 만족시킬 실행 기회를 제공하지 않는다는 것**이다.

## 원본 6건의 근거

시각 차이는 각 검토와 동일 observation·plan의 `fast decision started` 사건을 기준으로 계산했다. 단위는 ms다. 시각은 로그에 기록된 UTC에서 차이만 계산했으며 표의 날짜는 한국 시간 기준이다.

| 단계 | 관찰 ID | 검토 시작이 decision보다 늦은 시간 | 검토 완료가 decision보다 늦은 시간 | 최종 사유 |
|---|---|---:|---:|---|
| 1 | `obs-3fda456cc3` | 1.944 | 2.020 | `stale_context` |
| 2 | `obs-9d35a3dc50` | 1.865 | 1.958 | `stale_context` |
| 3 | `obs-e646acf819` | 1.940 | 2.038 | `stale_context` |
| 4 | `obs-2944688eaf` | 1.990 | 2.101 | `stale_context` |
| 5 | `obs-4634ab4ec4` | 2.122 | 2.246 | `stale_context` |
| 6 | `obs-ad3bf4e735` | 2.286 | 2.404 | `run_finished_unconsumed` |

원본은 로컬의 `runs/latest-pr-integration-20261015/20261015T145603-83f78314/brain_tasks.jsonl`, `brain_stages.jsonl`, `memory.jsonl`이다. 검토 결과를 원본 기억에 넣은 기록은 6건 모두 0건이었다. 모든 검토의 run ID는 일치하고 참조 기억 ID도 원본 로그에서 확인됐으며, 참조 기억 순번은 snapshot 순번 이하였다. 생성 실패·교차 실행·출처 누락 때문에 폐기된 사례가 아니다.

계획 검토의 생성 stage는 `plan_review`지만, 메모리에 전달할 출력 kind는 의도적으로 `reflection`이다. [SlowLoop 356–380행](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/slow_loop.py#L356-L380)의 반환과 Brain의 허용 kind가 맞는다. 이 이름 차이로 결과를 버린 것이 아니다.

## 실제 runner를 통과한 재현과 대조

사용자 증상과 같은 경로를 검증하기 위해 `run_study()`를 직접 실행하는 임시 harness를 사용했다. `max_steps=2`, 무료 Mock, Wonder 비활성화, 격리된 로컬 fixture다. 계획 검토가 적어도 1건 decision에 도달해야 한다는 assertion을 둬 현재 문제에서 실패하도록 했다.

```sh
.venv/bin/python /private/tmp/persona-plan-review-20261016/probe.py
```

첫 baseline은 검토 0/2 채택으로 assertion 실패했다. 별도 실행으로 반복해도 0/2였다. 두 실행 모두 첫 검토는 `stale_context`, 마지막은 `run_finished_unconsumed`였다.

| 조건 | 실제 실행 ID | 채택 | 검토 생성 memory가 같은 계획의 decision 입력 ID에 포함 |
|---|---|---:|---:|
| 현재 runner | `20261015T154759-ca80ac9f` | 0/2 | 0/2 |
| 현재 runner 반복 | `20261015T155102-f5b0d58a` | 0/2 | 채택 memory 없음 |
| decision 직전 worker 완료 대조 | `20261015T154837-1d9906da` | 2/2 | 2/2 |

대조 실행은 저장소 코드를 수정하지 않고 임시 함수 복사본에 **decision 직전 `await slow.worker` 한 줄만** 넣었다. 같은 plan·observation·version 보호 조건과 기존 단일 worker는 유지했다.

```sh
.venv/bin/python /private/tmp/persona-plan-review-20261016/probe.py --wait-before-decision
```

baseline의 첫 검토는 예약 반환 665.984ms, decision 경계 665.986ms, 검토 시작 667.906ms, 완료 667.971ms였다. 즉 경계를 검사할 때 검토는 대기 중이었다. 대조에서는 검토 완료 732.510ms 다음에 decision 경계 732.544ms가 발생하여 채택됐다.

대조의 첫 검토 출력 `stage-plan_review-814664e1fdd0437992c21c979692cddd`는 기억 `m-5-665199ffd5`가 됐고, decision `stage-decision-90ab287315d84f80bffe1819cf10e179`의 `source_memory_ids`에 들어갔다. 두 번째도 기억 `m-11-e550b9c88c`가 해당 decision 입력에 들어갔다. `adopted` 배지만 확인한 것이 아니라 **실제 전달한 입력 ID까지** 대조했다. 이 기록은 모델 내부가 조언을 따랐거나 행동 품질이 좋아졌다는 뜻은 아니다.

이 대조는 원인 분리를 위한 진단이며 구현안이 아니다. 전체 worker 대기는 앞선 성찰·중요도 작업까지 기다릴 수 있으므로 그대로 적용하면 지연·예산·종료 정책을 바꾼다. `sleep`을 임의로 넣는 방식도 실제 모델 지연을 보장하지 않는다.

임시 harness와 상세 결과는 `/private/tmp/persona-plan-review-20261016/`에 있다. 인증정보·유료 호출·기업/사람 데이터는 사용하지 않았다. 임시 실행 로그는 저장소에 추가하지 않는다.

## 다른 가설과 기존 검사가 놓친 부분

| 가설 | 예측과 확인 | 판단 |
|---|---|---|
| 예약 후 실행 기회 부재 | decision 이전에 worker가 완료하도록 하면 같은 보호 조건으로 채택돼야 함 → 0/2에서 2/2, 입력 ID도 포함 | 직접 원인 확인 |
| 중요도·성찰의 단일 큐 대기 | 큐 대기는 지연을 더할 수 있음. 동일 큐를 유지한 대조에서 채택되며, 현재 경계는 큐가 비어도 예약 직후 완료 검사를 함 | 추가 지연 요인, 이번 0/6의 필수 원인은 아님 |
| 결과 형식·출처 유효성 문제 | 유효성 문제면 기다려도 계속 폐기돼야 함 → 보호 조건을 유지한 대조에서 모두 채택; 원본 6건도 출처 확인 | 이번 원인 아님 |

[기존 정확한 계획 채택 테스트](../../tests/test_brain.py#L127-L143)는 decision 전에 `await brain.slow.worker`를 직접 호출한다. Brain의 유효성 조건을 확인하는 단위 테스트로는 유효하지만, 기다리지 않는 실제 runner 순서를 재현하지 않는다. 관련 보호 조건 검사 4개는 이번 진단에서 `4 passed in 0.10s`였다. 정상 단위 검사와 실제 경로의 미소비가 동시에 존재할 수 있었던 이유다.

## 후속 구현 전에 결정할 사항

1. **이번 계획을 현재 행동 전에 검토하는 기능인가?** 그렇다면 해당 검토 ID만 기다리는 명시적 대기 예산, 타임아웃 후 진행 정책, stop/cancel·전체 run 시간·호출 예산을 정해야 한다. 검토 결과 준비 뒤 decision 경계를 열거나 경계 직전에 다시 소비하도록 설계해야 한다.
2. **비동기로 다음 계획에 참고하는 기능인가?** 그렇다면 현재 exact-plan 검토와 다른 의미다. 과거 조언을 현재 화면·목표에 다시 검증하는 별도 advisory/retrieval 경로와 소비 로그가 필요하다. observation/plan 보호 조건을 무작정 제거하면 안 된다.
3. 선택한 정책을 실제 `run_study()` 경로에서 검증한다. 생성 완료뿐 아니라 해당 검토의 기억 ID가 예상 단계 입력에 들어가는지, 오래된 결과는 제외되는지, 지연·예산·중지 때 결과가 어떻게 기록되는지 확인해야 한다. 그 뒤 Slow 빈도·검색 가중치 실험을 시작한다.

현재 진단은 **원인 확인 완료 / 정책 선택·수정 미실시**다. Mock 0/6은 구현 결함을 찾은 결과이지 실제 LLM 성능이나 인간과의 일치도를 입증한 결과가 아니다.

## 별도로 발견한 집계 후속

원본 실행의 `summary.brain.slow.events.discarded`는 7건(계획 검토 6 + 성찰 1)인데 `summary.brain.adoption.discarded`는 5건이다. [경계 소비](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/brain.py#L153-L157)는 누계를 더하지만 [종료 미소비 처리](https://github.com/2026-2-1/Persona/blob/a031932fd1b0d11bf40f6fb7f13a7bf7c2653f6a/src/uxagent/brain.py#L103-L108)는 사건만 기록하고 이 누계에는 더하지 않는다. 종료 미소비 2건이 차이를 만든다.

이는 계획 검토 0/6의 원인과 별개인 **요약 집계 불일치**다. 수정하지 않았으며, 후속에서 지표 정의와 함께 정리해야 한다. 현재 폐기 사유별 집계는 원본 `brain_tasks.jsonl`의 작업별 최신 상태를 기준으로 읽는다.
