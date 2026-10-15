# [phase:1] 기억 중요도 비동기 산정

GitHub: [#40](https://github.com/2026-2-1/Persona/issues/40)

## 구현 범위

- 새 2.0 기억은 `importance=null`로 저장하고 Fast가 즉시 검색할 수 있게 한다. Slow worker가 persona, intent, 현재 계획과 기억 본문을 사용해 각 기억에 1~10점 중요도를 산정한다. [UXAgent 원본](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd)의 LLM 산정 방향을 따른다.
- 점수는 같은 memory ID와 순번에 적용한다. 원본 `memory.jsonl`은 수정하지 않고 `BrainStageRecord`, `BrainTaskEvent`, `MemoryChangeEvent`로 결과와 출처를 남긴다.
- Slow 호출은 Fast를 막지 않고 공통 요청·토큰 예산을 사용한다. 예산 소진·호출 실패·종료 취소는 작업 상태로 남기며, 점수는 `null`로 유지한다. 제거된 기억의 늦은 점수는 적용하지 않는다.
- 활성 기억 64개 기본 상한·최근 10개 과업 기억 보호·별도 최근 행동 입력을 유지한다. 검색 가중치와 미산정 기억 보존 정책의 추가 조정은 #54·#55에서 다룬다.

## 검증과 제한

- 원본 ID·순번 보존, 검색 가능성, Slow 호출·공통 예산, 제거 뒤 늦은 응답, provider 모델 경로와 mock 통합을 확인한다.
- 기억마다 추가 모델 호출이 발생하므로 실제 유료 API 비용과 실행 시간은 늘 수 있다. 유료 API 비용과 실제 사이트 행동은 mock 검사로 검증하지 않는다.
