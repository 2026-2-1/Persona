# Task 06 — Memory Stream과 비동기 Slow Loop

상태: 구현 완료; live embeddings 검증 대기 | 선행: 05 | 단계: 논문 구조 확장

## 목표

최근 몇 단계만 읽는 MVP에서 벗어나 관련 기록을 검색하고, 브라우저 실행을 막지 않는 성찰을 추가한다.

설계 연결: 논문 §3.2.1–3.2.2. 아래 정규화·가중치·주기·동시성 규칙은 프로젝트 제안이며 논문 설정값이 아니다.

## 구현 순서

1. append-only MemoryEntry 저장.
2. 최근성 검색 → 중요도·관련도 검색 추가.
3. 동기 Reflection 한 번으로 입출력 확인.
4. background task로 전환.
5. 필요할 때 Wonder와 모듈 분리 모드를 추가.

## MemoryEntry

```json
{
  "memory_id": "m-0001",
  "seq": 1,
  "run_id": "run-001",
  "kind": "observation",
  "text": "검은색 가방 2개와 각 가격을 확인했다.",
  "source_step_ids": [2],
  "source_observation_ids": ["obs-0003"],
  "created_at": "2026-10-07T14:30:00Z",
  "created_monotonic_ms": 5200,
  "based_on_seq": 0,
  "importance": null,
  "embedding_ref": null,
  "content_status": "observed"
}
```

kind는 observation/plan/action/reflection/wonder를 사용한다. content_status는 observed 또는 generated로 구분한다. 생성된 생각이 관찰 사실로 바뀌지 않게 한다. importance와 embedding은 나중에 계산할 수 있다.

## 검색 설계

- 최신 관찰, persona, task는 검색과 무관하게 항상 전달한다.
- 메모리에서 최대 8개를 검색하고 같은 source step의 중복을 줄인다.
- 임베딩은 최초 필요 시 한 번 생성하고 메모리 ID별로 캐시한다.
- 작은 실험은 메모리 내 배열과 JSONL로 충분하다. 벡터 DB를 도입하지 않는다.
- embeddings API를 쓰면 비용/토큰을 공통 예산에 포함한다.

자체 초기 점수 제안:

```text
I = importance / 5                       # 0~5 평가를 0~1로 정규화
R = clip((cosine_similarity + 1) / 2, 0, 1)
C = exp(-ln(2) * age_seconds / 60)       # 반감기 60초
score = (wI*I + wR*R + wC*C) / 사용 가능한 가중치 합
```

Fast 가중치 `(0.2, 0.3, 0.5)`, Slow 가중치 `(0.3, 0.5, 0.2)`로 시작한다. 타입별 가중치는 모두 1로 두고 후속 실험에서만 조정한다. importance 미계산을 0점으로 취급하지 않고 해당 항을 제외한다. 유효 점수가 없으면 최신성으로 fallback하고 로그에 표시한다.

논문 식을 그대로 구현했다고 표기하지 않는다. monotonic 시간과 단위를 명시하고, 테스트에서는 clock을 주입한다. API 응답이 느려져도 기억 내용이 달라지지 않도록 저장과 검색 시점을 기록한다.

## Reflection 계약

입력: persona, task, 특정 seq까지의 메모리 snapshot, 최근 실행 오류.

출력:

```json
{
  "based_on_seq": 12,
  "insights": [
    {"summary": "현재 필터로는 조건에 맞는 결과를 찾지 못했다.", "source_memory_ids": ["m-0010", "m-0012"]}
  ],
  "next_focus": "현재 선택된 가격 필터를 확인한다."
}
```

실행할 target ID를 반환하지 않는다. 오래된 화면의 구체적인 클릭을 예약하지 않고, Fast Loop가 최신 관찰로 다음 행동을 선택한다. 최대 insight 3개·짧은 설명으로 제한한다.

## 비동기 실행 규칙

- [ ] 5개 행동 시도마다 또는 반복 오류 발생 시 Reflection을 요청한다. 기본 trigger는 설정 가능하다.
- [ ] 한 run에서 Slow 작업은 최대 1개만 실행한다. 진행 중이면 새 요청을 합치거나 건너뛴다.
- [ ] 시작 시 immutable snapshot과 based_on_seq를 고정한다.
- [ ] Fast Loop는 완료를 기다리지 않는다.
- [ ] 완료한 성찰은 메모리에 append하고 이후 결정부터 사용한다.
- [ ] 완료 시점의 seq도 기록한다. 과거 시점에 이미 존재했던 것처럼 소급 삽입하지 않는다.
- [ ] Fast/Slow의 API 호출 예산을 하나의 잠금된 budget manager로 관리한다.
- [ ] Slow 실패는 로그만 남기고 Fast 실행은 계속한다. 전체 예산·실행 시간 소진은 runner 종료 조건이다.
- [ ] 종료 시 진행 중 Slow 작업을 취소하고 상태를 기록한다.

## Wonder·모듈 분리

Wonder는 `enable_wonder=false`가 기본이다. 활성화하면 persona 관련 짧은 연상 1개를 generated 메모리로 남기고 observed 사실이나 성공 근거로 쓰지 않는다. 이 기능은 인간다움이 검증되었다는 의미가 아니다.

`fast_mode=split`을 추가할 경우 Perception → Planning → Action을 별도 호출로 구성한다. 최종 AgentDecision과 executor 계약은 유지한다. 모듈을 나눴다는 이유로 성능 개선을 가정하지 않고 09에서 비교한다.

## 수용 검사

- 고정 시계·가짜 임베딩으로 검색 순위를 검증한다.
- importance=null인 항목도 최신성이 높으면 검색된다.
- Slow 응답을 의도적으로 늦춰도 Fast Loop가 다음 단계를 진행한다.
- 늦게 도착한 성찰이 과거 행동을 덮어쓰지 않는다.
- 동일 메모리 임베딩을 중복 호출하지 않는다.
- Fast/Slow 동시 요청이 예산을 이중 소비하지 않는다.
- Slow를 꺼도 05의 동작이 유지된다.

산출물: memory store/retriever, Reflection prompt, Slow task coordinator, 기능별 config와 로그.
