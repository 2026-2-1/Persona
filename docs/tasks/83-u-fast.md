# #83 U Fast 판단 전환

후속 #84 작업 브랜치는 아래의 최초 reflection 연결을 [U Slow 반복](84-u-slow.md)으로 교체한다. 이 문서의 #84 미구현 표기는 #83 작성 당시 범위다.

이슈: [#83](https://github.com/2026-2-1/Persona/issues/83). Qwen 선행: [PR #91](https://github.com/2026-2-1/Persona/pull/91), `264bd985ce3bd1744d4e692af52efdc719e61b00`. 구현 브랜치는 `feat/83-u-transition-01`이다. prototype 병합이나 실제 GPU 과업 성공을 뜻하지 않는다.

## 실행 순서와 책임

| 차례/단계 | 모델 입력 | 응답·기억 | 다음 단계 |
| --- | --- | --- | --- |
| 최초 인식 | HTML을 JSON 문자열로 직렬화, U deny list 치환 | observations의 첫 항목 → Observation | 최초 한 번 Slow 시작 요청 |
| 후속 feedback | persona, 직전 raw_action JSON 문자열, 직전 plan 문자열, 현재 HTML | thoughts 전부 → Thought | perceive와 gather로 합류 |
| 후속 인식 | feedback과 같은 현재 HTML, perceive에만 deny list 적용 | 첫 observation → Observation | feedback과 공유 기억 저장 완료 후 계획 |
| 계획 | persona, intent, 기억 문자열, 차례 timestamp, old_plan/N/A | plan/rationale/next_step → rationale Thought, Plan | next_step으로 행동 기억 검색 |
| 행동 | valid_targets, persona, intent, plan, next_step, 원래 HTML, recent_memories | 모든 actions → generated Action/raw_action | 첫 번째만 기존 실행기에 전달 |

`Brain.forward`가 이 흐름을 소유한다. `FastLoop.perceive_page/feedback/make_plan/act`는 생성과 응답 검증을 맡는다. 모델 역할 small/large는 현재 선택한 동일 제공자·모델로 매핑되며 GPU는 LocalQwenProvider / persona-qwen을 유지한다. 일반 AI 조건에는 persona의 공통 constraints/intent만 직렬화한다. evaluator 정답·프로필은 모델 입력에 넣지 않는다.

U 프롬프트 네 개는 고정 커밋에서 변경 없이 `src/uxagent/prompts/u_fast/`로 복사했고 wheel의 package-data에 포함한다. 요청에는 기존 호출 로그용 FAST_STAGE 표식과 JSON 응답 지시가 추가된다. 기존 `FastLoop.decide`, `perceive`, `plan`, `decide_action`은 이전 API와 선택적 Jev 후보 선택 호환용이다. **run/batch/compare의 실행기는 해당 옛 3단계 조율 API를 호출하지 않고 Brain.forward를 사용한다.** Jev만 기존 후보 선택/생성 fallback 결과를 U 제안으로 바꾸며, GPU 경로에는 후보 선택이 없다.

## 이번 이슈에 포함한 선행 어댑터

- 스키마: UPerception/UFeedback/UPlan/UAction/UActions, thought, 차례 timestamp/raw_action, 원본 model_response. 기존 steps의 action/result/evaluation과 구버전 읽기는 유지한다.
- 기록 단계 이름은 perception/feedback/plan/decision으로 남기고 실제 U JSON을 보존한다. ID와 plan version은 호스트의 연결 정보이며 모델에게 생성하도록 요구하지 않는다.
- Brain의 현재 관찰·계획 버전 gate와 Slow 결과 우선 삽입을 제거했다. 완료된 기존 Slow 결과는 공유 기억으로 발행하고 이후 정상 검색에 맡긴다. 첫 인식 직후 기존 reflection 시작만 연결한다. 기존 plan_review를 Fast마다 예약하지 않는다.
- 기억 검색 질의와 최근 포함 창은 U에 맞춘다. plan은 intent, Observation 최근 3차례와 Action/Plan/Thought 최근 5차례를 먼저 포함한 뒤 순위 검색 결과를 덧붙인다. U처럼 같은 기억의 중복 포함도 보존한다. act는 next_step으로 검색하며 같은 source step이라는 이유로 서로 다른 기억을 제거하지 않는다. plan 종류 가중치는 action/plan/thought/reflection=10, act는 observation=0·action/thought=10이다.
- 액션 어댑터는 click/type/hover/select/clear/key_press/goto_url/back/switch_tab/close_tab/terminate를 현재 실행 모델로 변환한다. #87 후속으로 forward/refresh/new_tab·target 없는 key_press와 전체 U action 집합을 연결했다. type+enter는 fill 후 Enter로 실행한다.
- 제안은 도구 실행 전에 기록한다. 실행 실패 이후에도 raw_action은 제안으로 남으며 도구 실패를 제안의 관찰 사실로 바꾸지 않는다. terminate는 기존 Finish completed로 변환하지만 독립 성공과 구분한다.

## U 원본과 남는 차이

| 항목 | 이 브랜치의 처리·다음 책임 |
| --- | --- |
| Crime/crime/Security/security 치환 | U 그대로 perceive 입력에서만 치환, feedback/act의 HTML에는 미적용 |
| 여러 observations | U처럼 첫 항목만 소비; 비거나 첫 문자열이 비면 명시적 오류, 관찰을 지어내지 않음 |
| plan 재시도 | U의 무한 반복 대신 기존 1회 JSON 복구·전송 오류 재시도/예산/실행 시간 한도 유지. next_step을 문자열로 검증 |
| 빈/복수 actions | 빈 배열은 기존 1회 JSON 복구 후 실패. 복수 배열은 U처럼 모두 제안 기억에 저장하고 첫 번째만 실행. 다음 feedback의 last_action은 U처럼 마지막 제안이므로 실제 실행과 다를 수 있음 |
| act의 valid_targets 결함 | U 코드 그대로 inputs/selects도 clickable 목록으로 만든다. 올바른 목록으로 몰래 바꾸지 않았다. 실제 입력/선택 대상을 찾는 데 영향을 줄 수 있음 |
| 동시 호출 한쪽 실패/취소 | U gather 흐름에 형제 task 취소·합류 정리를 추가. 실패 뒤 늦은 기억 쓰기·미정산 요청을 남기지 않음 |
| 토큰 한도 | U perceive는 64,000을 요청하지만 현재 설정 max_output_tokens는 유지. 실제 Qwen의 문맥/출력 한도는 검증하지 않았고 큰 페이지의 관찰 완전성도 보장하지 않음 |
| 기억 순위 점수 | 최근 기억·종류 가중치·질의 연결만 완료. 기존 점수/선택적 embedding 계산은 #85에서 dot-product·차례 최신성·중요도로 전환해야 함. GPU embed 미지원과 활성 64개 상한 유지 |
| 관찰 DOM와 행동 실행 | #86 U semantic DOM·#87 U 행동/접근 정책 적용. Qwen의 실제 전체 과업 성공은 별도 검증 대상 |
| Slow | 기존 reflection을 처음 한 번 시작하는 연결. reflect→wonder→memory.update 반복과 1% Wonder 제거는 #84에서 구현 |
| 종료/평가 | 기존 실행 중 평가와 성공 시 조기 종료 유지. AI terminate 후 별도 평가는 #89에서 구현 |

## 검증

`tests/test_u_fast.py`는 첫/후속 입력·기억 순서, Event 기반 feedback/perceive 동시성, 일반 조건 분리, 빈/잘못된 출력, 실제 usage 정산·복구·예산, 동시 호출 실패/취소 정리, 미지원 행동 제안 보존, 실제 브라우저 type+Enter를 검증한다. runner 실패 회귀는 도구 호출 전에 제안 기억 파일이 존재하는지 확인한다. 기존 데카트론 테스트는 U 응답을 쓰면서 상품 일치/불일치·평가 프로필의 판정을 유지한다.

실제 실행 결과는 [verification](../verification.md)에 기록한다. Mock/가짜 제공자 통과를 실제 GPU·공개 데카트론 성공으로 간주하지 않는다.

2026-10-18 실제 공개 데카트론 첫 화면에서 위 토큰 한도 문제가 발생했다. Qwen 전용 큰 화면 경로는 원본 관찰 기록을 유지하면서 모델 입력만 보이는 텍스트·조작 대상 목록과 짧은 ID로 바꾸고, 행동 제안의 ID를 원래 semantic ID로 복원한다. Perception 지시도 서버의 실제 512토큰 출력 한도에 맞춰 짧게 만든다. 이 경로는 U의 전체 HTML 입력과 모든 문구 서술 계약을 충족하지 않으며 다른 제공자의 U 입력은 유지한다. [실패·검증 기록](../troubleshooting.md)을 참고한다.

## 원본 링크

- [AgentPolicy.forward](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/model.py#L139-L196)
- [perceive/feedback](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L69-L134)
- [plan/act](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L248-L355)
- [기억 검색](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/memory.py#L155-L226)
- [프롬프트 원본](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/shop_prompts)
