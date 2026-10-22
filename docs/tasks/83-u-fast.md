# #83 U Fast 판단 전환

## 2026-10-22 행동별 양식과 인자 오류 재요청

초기 행동 프롬프트는 지원하는17개 행동의 JSON 예시와 선택 필드, raw_type/type 차이를 명시한다. 예시는 UAction으로 검증하며 기존2400자 미만 제한을 유지한다. raw_type은 현재 포커스 입력의 text/description만 허용하고, 대상을 지정하거나 Enter까지 보내려면 type을 선택하도록 안내한다.

UAction.argument_contract의 필수/허용 인자 집합을 스키마 검증과 재요청에 공유한다. 재요청은 해당 행동의 허용 필드만 넣은 빈칸 템플릿과 required_fields/allowed_fields/unexpected_fields/missing_fields를 제공한다. 원본에 target/enter가 붙은 raw_type이면 유효한 원래 대상·텍스트·Enter를 보존한 type 대안도 제시한다. 템플릿은 실행 행동이 아니며 모델이 다시 선택해야 한다. 코드는 대상 삭제나 행동 변환을 자동 집행하지 않는다. 필요한 좌표가 없으면0으로 채우지 않고 null로 남긴다.

기존 최대1회 재요청·JSON/스키마 검사·usage/원문 로그·예산/취소 계약을 유지한다. 두 번째도 invalid면 제안/실행으로 전달하지 않는다. 실제 실패 근거는 `20261021T142323-1302c49e`에서 두 번 반복된 raw_type+target이다. 검증 결과는 verification.md를 따른다.

## 2026-10-20 실제 행동 실패 피드백 후속

사용자 요청으로 실제 실행기의 ActionResult를 다음 feedback·plan·decision에 별도 last_action_result로 전달한다. 마지막 제안 대신 실제 실행되는 첫 제안이 last_action이며 계획·행동에도 결과와 함께 제공한다. 현재 메뉴/팝업은 계획의 page_context에도 제공해 이전 계획이 열린 상위 메뉴를 반복 지시하지 않게 한다. 제안 기억은 기존처럼 모두 생성 기록으로 남고, 실행 결과는 steps에 보존한다. 결과가 없으면 성공으로 추정하지 않으며 실패한 논리 단계를 (next)로 무조건 넘기라는 지시를 제거했다. U 원본의 입력에 실행 사실을 추가한 차이다. evaluator 답이나 실행 허가 게이트를 모델에 추가한 것은 아니다.

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
| act의 valid_targets 결함 | #83 당시 U 코드 그대로 inputs/selects도 clickable 목록으로 만들었다. 2026-10-20 검색 경로 보완에서 실제 input/select 목록으로 교정했다. |
| 동시 호출 한쪽 실패/취소 | U gather 흐름에 형제 task 취소·합류 정리를 추가. 실패 뒤 늦은 기억 쓰기·미정산 요청을 남기지 않음 |
| 토큰 한도 | U perceive는 64,000을 요청하지만 현재 설정 max_output_tokens는 유지. 실제 Qwen의 문맥/출력 한도는 검증하지 않았고 큰 페이지의 관찰 완전성도 보장하지 않음 |
| 기억 순위 점수 | 최근 기억·종류 가중치·질의 연결만 완료. 기존 점수/선택적 embedding 계산은 #85에서 dot-product·차례 최신성·중요도로 전환해야 함. GPU embed 미지원과 활성 64개 상한 유지 |
| 관찰 DOM와 행동 실행 | #86 U semantic DOM·#87 U 행동/접근 정책 적용. Qwen의 실제 전체 과업 성공은 별도 검증 대상 |
| Slow | 기존 reflection을 처음 한 번 시작하는 연결. reflect→wonder→memory.update 반복과 1% Wonder 제거는 #84에서 구현 |
| 종료/평가 | 기존 실행 중 평가와 성공 시 조기 종료 유지. AI terminate 후 별도 평가는 #89에서 구현 |

## 검증

`tests/test_u_fast.py`는 첫/후속 입력·기억 순서, Event 기반 feedback/perceive 동시성, 일반 조건 분리, 빈/잘못된 출력, 실제 usage 정산·복구·예산, 동시 호출 실패/취소 정리, 미지원 행동 제안 보존, 실제 브라우저 type+Enter를 검증한다. runner 실패 회귀는 도구 호출 전에 제안 기억 파일이 존재하는지 확인한다. 기존 데카트론 테스트는 U 응답을 쓰면서 상품 일치/불일치·평가 프로필의 판정을 유지한다.

실제 실행 결과는 [verification](../verification.md)에 기록한다. Mock/가짜 제공자 통과를 실제 GPU·공개 데카트론 성공으로 간주하지 않는다.

2026-10-18 실제 공개 데카트론 첫 화면에서 위 토큰 한도 문제가 발생했다. Qwen 전용 큰 화면 경로는 원본 관찰 기록을 유지하면서 feedback/행동 모델 입력만 보이는 텍스트·조작 대상 목록과 짧은 ID로 바꾸고, 행동 제안의 ID를 원래 semantic ID로 복원한다. 후속 수정에서는 큰 화면 perception이 원본 HTML의 내부 parser 속성만 제외한 뒤 1,400자 이하 조각으로 순차 요청하고, 각 결과를 다시 같은 크기로 나눠 한 관찰이 남을 때까지 합친다. 모델의 실제 512토큰 출력 한도에 맞춰 조각별 응답을 240자 이하로 요청하며, 모델이 500자를 넘게 반환하거나 빈 관찰을 반환하면 조용히 자르지 않고 오류로 남긴다. 각 요청의 단계·조각 번호와 입력/응답은 기존 로컬 호출 로그에 보존한다. 이 경로는 U의 전체 HTML 입력과 모든 문구 서술 계약을 충족하지 않으며 요약 손실 가능성이 남는다. 다른 제공자의 U 입력은 유지한다. [실패·검증 기록](../troubleshooting.md)을 참고한다.

2026-10-19 라이브 Qwen이 첫 조각에서 관찰 5개를 반환해 기존 정확히 1개 조건에 막혔다. 조각 내 모든 비어 있지 않은 관찰을 순서대로 결합한다. 조각 요약 전체가 1,400자 이하가 되면 마지막 재요약 호출 없이 그대로 한 관찰로 전달한다. 더 크면 다시 나누어 요약한다. 실행기는 행동 후 기록한 관찰을 다음 Fast 차례에 재사용해 중복 DOM 대기를 없애고, 종료 후 독립 평가용 최종 관찰은 별도로 찍는다. [실제 기록](../verification.md)을 참고한다.

2026-10-19 후속으로 큰 Qwen 화면의 perception도 기존 feedback/decision에서 쓰던 규칙 기반 텍스트·컨트롤·짧은 ID 표현을 먼저 생성한 다음 조각으로 읽는다. 이미지 alt/title과 `article`/`li`/`section`/`tr` 경계도 보존한다. 원본 observation JSON/PNG·원래 semantic ID는 유지하고, Qwen perception의 비공개 호출 기록에는 실제 압축된 입력을 남긴다. 작은 화면과 다른 제공자의 U HTML 입력은 그대로다. 이 입력 표현은 U 전체 정리 HTML과 다르며 문맥·이미지 의미를 완전히 보존한다는 주장은 하지 않는다. [측정과 한계](../verification.md)를 참고한다.

2026-10-19 실제 Qwen이 큰 화면 조각의 마지막 닫는 괄호를 `}]`로 뒤집어 두 번 반환한 경우를 확인했다. 조각 프롬프트에는 단일 240자 이하 관찰과 닫는 순서를 명시한다. 파서는 GPU 조각 응답의 완전한 JSON 뒤 백틱 또는 `observations` 배열의 정확한 마지막 괄호 역순만 교정한 뒤 UPerception으로 검증한다. 원문 호출 로그와 그 밖의 문법 오류의 기존 복구/실패 처리는 유지한다. [재현·검증](../troubleshooting.md)을 참고한다.

같은 날 후속 실행에서 Qwen이 배열의 마지막 `]` 자체를 빠뜨리고 복구 요청에도 반복하는 사례를 확인했다. GPU 조각의 `observations` 객체가 마지막 문자열 뒤 `"}`로 끝나는 경우에만 `]`를 넣은 후보를 다시 파싱·검증한다. 본문 안쪽 문법 오류는 기존 모델 복구/실패 처리에 남긴다.

2026-10-20 검색·메뉴 보완: U 원본의 `valid_targets.inputs/selects`가 clickable을 재사용하는 결함은 실제 input/select 관찰 목록으로 교정했다. 데카트론의 판촉 placeholder가 붙은 상단 입력은 실제 `data-cy="search-bar-desktop"` 근거로 “상품 검색”이라고 관찰한다. 사용자 후속 결정에 따라 `available_search_inputs` 계획 필드와 검색 우선 지시는 제거했다. 검색을 선택한 경우에는 클릭 → Enter 없는 입력 → “모든 결과 보기” 클릭이 필요하다고 행동 모델에 설명한다. GPU용 큰 화면은 별도 `<navigation>`에 각 메뉴 항목의 보이는 열 경로와 짧은 대상 ID를 제공한다. 같은 이름의 러닝화도 `러닝 > 러닝화`와 `러닝 > 남성 > 러닝화`로 구분하며 세 번째 열은 `러닝 > 남성 > 러닝화 > 로드러닝/조깅`으로 표시한다. 실제 앱 실행기에서 검색 결과와 4단계 카테고리 이동을 각각 확인했다. 이는 U 원본의 입력 표현·행동 대상 목록과 다르며 Qwen 자율 전체 과업은 재검증하지 않았다.

## 원본 링크

2026-10-19 후속: GPU 큰 화면의 feedback/act projection은 hover 전용 대상을 포함하고 각 조작 요소의 role·이름·현재 값·enabled/checked/focused·href와 select option의 실제 value/label을 보존한다. 모든 대상은 같은 짧은 ID 복원표를 사용하며 원래 observation/ElementInfo는 수정하지 않는다. U의 기존 valid_targets 구성 정책은 바꾸지 않는다.

- [AgentPolicy.forward](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/model.py#L139-L196)
- [perceive/feedback](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L69-L134)
- [plan/act](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L248-L355)
- [기억 검색](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/memory.py#L155-L226)
- [프롬프트 원본](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/shop_prompts)

2026-10-21 공통 전송 전 검사: 인식/피드백/계획/행동과 JSON 수정 차례가 prepare_model_messages를 거쳐 Qwen 한도를 재검사한다. 초과한 기억·관찰·이전 계획만 계층 요약하고 고정 지시/페르소나/과업/행동 대상·실행 결과는 보존한다. 추가 호출은 prompt_summary/parent_stage로 기록하고 공통 예산을 사용한다. 원본 기록과 생성 요약은 구분한다.

2026-10-21 입력 검사2차: 고정 지침의 중복/예시를 줄이고 큰 대상 목록은 target_selection으로 관찰 구역→세부 컨트롤을 선택한다. 선택 자체는 행동/메모리 관찰 사실이 아니며 예산/호출 로그에만 추가한다. 같은 ID의 컨트롤 중복을 합치고 최종 제안의 원래 semantic ID 복원과 기존 실행 정책을 유지한다.
