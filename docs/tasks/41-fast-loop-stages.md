# [phase:1] Fast Loop의 인식·계획·행동 결정 분리

GitHub: [#41](https://github.com/2026-2-1/Persona/issues/41)

## 범위

- Fast Loop에서 perception, plan, action decision을 순서대로 별도 생성 요청으로 수행한다.
- perception과 plan은 생성 직후 활성 메모리에 저장한다. 다음 생성 단계는 시작 시점의 선택 기억을 입력으로 받는다.
- 단계별 입력에서 사용한 기억 ID와 결과, observation ID, plan ID를 `brain_stages.jsonl`에 기록한다.
- decision은 현재 observation의 ID/tab에 묶인 action 또는 finish 제안 하나만 반환한다.
- Jev 후보 선택과 Gemini 생성 경로, JSON 검증·재시도, 호출·토큰 예산을 유지한다.
- 기존 `steps.jsonl` 소비자를 위해 최종 결정 기록에 perception과 plan 텍스트를 함께 보존한다.
- 생성 모델은 행동 차례당 세 단계 요청을 사용한다. Jev는 인식·계획 생성과 후보 선택 요청을 별도 예산으로 센다.

## 범위 밖

- Brain 조율기와 Slow Loop reflection/plan review 예약
- 브라우저·ActionExecutor의 책임 변경
- Slow 작업의 대기열·snapshot 정책

## 검증

- Fast 단계별 fake provider 검사에서 요청 순서와 observation 참조를 확인한다.
- runner mock 실행에서 단계 기록, 중간 메모리 저장, 기존 독립 성공 판정을 함께 확인한다.
- Jev 선택/fallback, 잘못된 JSON 재시도, finish 오판 회귀를 유지한다.

구체 검사 결과는 [검증 기록](../verification.md)에 추가한다.
