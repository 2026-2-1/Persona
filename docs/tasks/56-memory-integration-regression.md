# [phase:1] 메모리 점수·상한·비동기 출처 종합 검증

GitHub: [#56](https://github.com/2026-2-1/Persona/issues/56)

## 통합 검증 범위

- 상한 10과 64의 로컬 fixture mock 실행에서 원본 `memory.jsonl`, 점수·제거 `memory_changes.jsonl`, `brain_tasks.jsonl`, `brain_stages.jsonl`, `llm_calls.jsonl`, 실행 요약을 함께 읽는다.
- 원본 기억 ID의 고유성, 생성 시 `importance=null`, 같은 ID의 1~10점 갱신, 활성 상한, 제거 사유, Slow 입력 출처 ID의 역추적, 공통 요청 예산과 호출 기록을 확인한다.
- Fast 계획 입력에서 검색 상위 기억 최대 6개와 최근 행동 이력이 별도 배열인지 확인한다. 빈 기억, 오래된 고점 기억의 최근 10개 보호에 따른 제거, 점수 동점·갱신은 메모리 정책 전용 테스트와 함께 검증한다.
- Slow snapshot 중 제거, 늦은 점수·embedding, 실패·예산·취소, 구버전 JSONL과 null 행동 기록의 호환은 #40·#47·#54·#55 전용 회귀와 전체 pytest에 포함한다.

## 실행 조건과 제한

- 결정적 mock/fake provider와 로컬 fixture만 사용한다. 실제 유료 API, 구독 로그인, 공개 사이트 성공, 사람 행동 유사성은 검증하지 않는다.
- 단일 실행에서 모든 비동기 경계가 발생하는 것은 아니다. 상한 충돌은 N=10 runner 실행으로, provider 지연·취소·제거 경합은 이벤트를 제어하는 전용 테스트로 분리해 재현한다.
