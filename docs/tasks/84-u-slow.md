# #84 U Slow·Wonder 반복

이슈: [#84](https://github.com/2026-2-1/Persona/issues/84). 선행: Qwen [PR #91](https://github.com/2026-2-1/Persona/pull/91), Fast [PR #92](https://github.com/2026-2-1/Persona/pull/92), `4e42109a94898fb772a7c214221115ce25b75d66`. 작업 브랜치는 `feat/84-u-transition-02`다. prototype 병합·실제 모델 과업 성공과 구분한다.

## 현재 실행 순서

첫 인식의 Observation 저장 뒤·첫 plan 전에 `ContinuousSlowLoop.start()`를 한 번 호출한다. 하나의 실행별 task가 다음을 반복한다. Fast는 이 task를 기다리지 않고 plan/act와 다음 차례로 진행한다.

| 단계 | 입력 | 결과 |
| --- | --- | --- |
| reflect | current_timestamp, 마지막 성찰 시작 이후의 활성 memories, persona | insights 문자열 전부를 generated Reflection으로 즉시 저장 |
| wonder | persona, 최근 활성 기억 최대50개를 U 형식으로 표현한 memories, intent | thoughts 0~3개를 generated Thought로 즉시 저장; 빈 배열 정상 |
| memory.update | 현재 활성 기억 중 미산정·미임베딩 항목의 ID별 snapshot | 설정된 embedding과 importance를 gather, 응답을 같은 활성 ID에만 적용 |

각 반복 완료 뒤 `asyncio.sleep(0)`으로 실행권만 양보한다. 시간 간격·확률 추첨·반복 횟수 제한을 도입하지 않는다. Python 조율기는 Slow 전체 완료를 기다리지 않는다. 단일 GPU 서버의 실제 요청 경합·동시 처리 성능은 미검증이다. 오류/예산 소진은 worker를 failed/budget_exceeded로 끝내고 원인을 남긴다. 정상 실행 종료·중지·시간 초과에서는 task와 갱신 하위 task를 취소한 뒤 await한다. 취소한 호출을 완료/성공으로 표시하지 않는다.

## 모델·메모리 계약

- U 고정 커밋의 reflect/wonder/memory_importance 프롬프트 세 개를 `prompts/u_slow/`에 원문 그대로 포함한다. 로그용 `SLOW_STAGE` 표식과 JSON 지시 외에 별도 요약/보호 프롬프트를 추가하지 않는다.
- `UReflection.insights: list[str]`, `UWonder.thoughts: list[str]`(최대3개), `UImportance.score: int`(1~10)·rationale를 검증한다. importance 입력의 memory는 원문 문자열이며 persona/intent/current plan을 포함한다. 한 갱신 batch의 계획은 입력 구성 시점 값으로 고정한다.
- Reflection/Thought는 stage 경계나 observation/plan version 검증을 기다리지 않는다. 생성 단계의 source ID·snapshot 순번은 기록용이며 현재 활성 상태가 아니어도 성찰 결과를 폐기하지 않는다.
- `MemoryStore.last_seq`는 배열 길이와 독립인 단조 순번이다. `since(cursor)`는 cursor보다 새로 생성됐고 아직 활성인 기억을 깊은 복사로 반환한다. 성찰 시작 시 cursor를 당시 last_seq로 이동한다. 응답 대기 중 추가된 기억은 다음 성찰에 들어간다. 이미 64개 상한으로 제거된 기억을 몰래 복원하지 않는다.
- `MemoryStore.update(score_new, embed_new)`는 갱신 작업끼리만 잠그며 Fast를 잠그지 않는다. 같은 snapshot의 embedding/importance를 함께 시작하고 한쪽 오류·취소 시 형제 작업을 취소·합류한다. 응답을 배열 위치로 적용하지 않는다. 제거된 ID의 늦은 결과는 새 기억에 붙이지 않고 데이터 갱신 폐기 사건을 남긴다. 이는 생성된 성찰의 사용 허가 gate와 다르다.
- 새 stage 기록은 원본 model_response와 generated 상태를 보존한다. memory_update·embedding 작업 사건을 기존 reader가 읽도록 kind를 추가했다. 과거 plan_review·1% WonderDrawRecord·Wonder 기억과 출력은 계속 읽는다.

## 제거한 새 실행 정책

- Fast별 reflection/plan_review 대기열, stage 경계 결과 회수·우선 삽입, stale-context 채택 판단.
- 1% draw/seed/parent draw와 당첨용 별도 task, persona-only Wonder, Wonder 전용 기억 종류·삽입 제한.
- 새 run에는 `wonder_policy=u_every_cycle`, `prompt_version=u-loops-1`을 남긴다. draw 파일과 실행 seed를 만들지 않는다. `enable_slow_loop`/`enable_wonder`의 과거 false 입력은 true로 정규화한다. `wonder_seed`/`reflection_every_actions`는 옛 설정을 읽기 위한 필드이며 새 스케줄러에서는 사용하지 않는다.

기존 `SlowLoop`의 큐 API는 명시적 이전 호출자 호환용으로만 남는다. 현재 runner는 해당 큐 클래스를 만들지 않고 `ContinuousSlowLoop`를 사용한다. 두 구현은 정책 없는 모델 호출 계측·append-only 사건 helper만 공유한다. Brain의 옛 회수 helper도 legacy 이름으로 구분하며 새 forward에서 호출하지 않는다.

## 포함한 선행 범위와 남은 작업

| 항목 | 이 브랜치의 범위 |
| --- | --- |
| 64개 상한·배열 커서 | 상한 유지, 단조 seq cursor 도입, 제거된 ID에 대한 늦은 점수/벡터 방지 |
| GPU Qwen 채팅 | 같은 persona-qwen 제공자·실제 usage·비용 미확인·요청/토큰 예산 유지; 자동 모델 교체 없음 |
| embedding 설정 없음 | 벡터를 만들거나 완료로 표시하지 않음. importance는 갱신하며 summary.embedding_status=not_configured |
| 실제 GPU embedding | 미지원 상태 유지. 실제 별도 제공자/model/차원과 검색의 dot-product·차례 최신성·중요도 공식은 #85 |
| 실제 embedding 설정 있음 | 기존 mock/live 지원 조합에서 갱신 경로 사용. 새 벡터 batch의 개수·차원 일관성·유한 숫자를 검사하고 actual usage/실패/취소를 기록 |
| 브라우저·평가 | #86/#87/#89 전까지 현재 DOM·행동 접근 검사·실행 중 독립 평가/조기 종료 유지 |
| UI·서버·비용·출력 | 재설계 없음. 새 사건 kind의 reader 호환과 모델 호출 계측만 연결; 전체 새/옛 기록 통합은 #90 |

## 오류·취소의 한계

모든 예약된 모델 요청은 응답 검증 실패·취소 때도 사용량 기록과 예산을 정산한다. 응답 토큰을 받기 전 취소하면 실제 토큰은 미확인으로 남는다. async worker와 갱신 하위 task가 종료된 뒤 파일을 닫으며 늦은 메모리 쓰기를 막는다. 기존 `urllib` 제공자는 `asyncio.to_thread`를 쓰므로 이미 시작된 원격 HTTP 자체를 강제로 중단하는 기능까지 추가한 것은 아니다. 해당 I/O는 기존 요청 timeout의 적용을 받으며, 원격 취소나 실제 청구 중단을 보장하지 않는다.

Mock은 합성 fixture 전용이다. 새 Slow 응답은 최초 성찰·Thought 뒤 빈 배열을 반환하는 시나리오이며, 즉시 응답으로 인한 CPU 독점을 피하도록 Mock 전송에만 1ms 지연을 둔다. 실제 스케줄러에는 이 지연이 없다. Mock 반복 수·호출 수를 GPU 성능/요금 측정으로 사용하지 않는다.

## 검증

`tests/test_u_slow.py`는 Event로 두 번 이상의 순환, 단일 worker, Fast의 두 판단과 겹침, 최근 50개, 64개 상한 뒤 성찰 cursor, 빈 새 기억·빈 insights/thoughts, 두 실행 분리, 갱신 중 기억 제거와 늦은 응답, 공동 갱신 취소·시작 직후 중지·JSON 실패·예산 소진을 확인한다. 기존 runner 회귀는 draw 부재·Thought 저장·반복 순서와 기존 기록 reader를 확인한다. 실제 명령과 결과는 [verification](../verification.md)에 기록한다.

## U 원본

- [실행별 반복·시작·close](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/model.py#L137-L212)
- [reflect](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L136-L164), [wonder](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L220-L246)
- [memory.update](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/memory.py#L59-L153), [프롬프트](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/shop_prompts)
