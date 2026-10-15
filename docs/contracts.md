# 평가·기록·결과 계약

이 문서의 일부 필드는 목표 계약이며 실행 코드에 아직 연결되지 않았다. [#39](https://github.com/2026-2-1/Persona/issues/39)의 기록 스키마와 실제 구현 상태는 아래를 따른다.

## Brain 기록 계약 (#39)

| 기록 | 버전·내용 | 현재 생성 여부 |
|---|---|---|
| `BrainStageRecord` | 1.0; 생성된 importance/perception/plan/decision/reflection/plan_review/wonder, 관찰·계획 버전·참조 기억과 시간 | Fast와 Slow 결과, 중요도 산정 결과를 `brain_stages.jsonl`에 기록 |
| `BrainTaskEvent` | 1.0; 실제 비동기 작업의 예약·시작·생략·생성 완료·채택·폐기·실패·취소 사건과 snapshot 출처 | Slow lifecycle 및 Brain 결과 채택/폐기를 `brain_tasks.jsonl`에 기록 |
| `MemoryEntry` | 구버전 입력은 1.0으로 읽음. 새 기록은 2.0이며 생성 단계·원본 기억 ID를 선택적으로 연결 | `MemoryStore`가 2.0 기록 생성 |
| `MemoryChangeEvent` | 1.0; 중요도 점수 갱신 또는 활성 메모리 제거의 원본 ID·점수·사유 | 활성 메모리 제거와 1~10점 중요도 갱신을 `memory_changes.jsonl`에 기록 |
| `WonderDrawRecord` | 1.0; 실행 seed·시작된 부모 Slow 작업 ID/종류·추첨 순번/값·당첨 시 Wonder 작업 ID | Wonder를 켠 실행에서 `wonder_draws.jsonl`에 작업별 한 건 기록 |

`StudyConfig.max_active_memories`는 기본 64, 허용 범위 10~64다. 활성 과업 기억의 최근 10개를 보호하고 Wonder를 먼저 제거한다. 나머지는 중요도 우선·동점일 때 생성 순번이 최신인 순서로 남긴다. 새 Wonder 때문에 과업 기억이 제거될 상황이면 생성 단계만 남기고 기억 채택은 폐기한다. `memory_limit`은 별도의 검색 반환 개수다. 원본 `memory.jsonl`은 제거·점수 갱신 시에도 보존하고, 제거 ID·사유·보존 점수 또는 1~10점 갱신은 `memory_changes.jsonl`에 기록한다. 구버전 `MemoryEntry` 1.0의 중요도는 0~5로 읽고, 새 2.0 기록은 미산정 `null`로 생성한 뒤 Slow가 1~10점으로 산정한다. Fast는 점수를 기다리지 않으며 미산정 기억도 검색한다. 실패·예산 소진·취소는 점수를 `null`로 두고 작업 사건을 남긴다. 현재 검색은 I/Q/R을 같은 가중치로 합치며 없는 요소는 합산에서 제외한다. Fast/Slow별 가중치 보완은 #54다.

#42의 성찰과 계획 검토는 각 작업 시작 시 활성 메모리를 깊은 복사하고 최대 snapshot 순번과 출처 ID를 기록한다. #43의 Brain은 Fast 각 단계 시작에서 완료 결과만 가져온다. Reflection은 같은 run의 유효한 snapshot provenance를 확인한 뒤 메모리에 채택한다. Plan review는 동일한 observation ID·plan ID·version의 decision 시작 전에 끝난 경우에만 generated memory로 채택하고, 그 외는 `discarded/stale_context`로 남긴다. plan review는 plan을 덮어쓰지 않으며 generated memory는 untrusted context로 Fast에 전달한다.

Slow는 실행별 단일 worker, 사용자 결정에 따른 무제한 대기열이다. Fast와 브라우저 실행은 Slow를 기다리지 않는다. 실행 종료 시 active/pending 작업은 `cancelled/run_finished`로 기록한다. 모델 생성이 끝난 상태(completed)와 Brain이 결과를 채택한 상태(adopted)는 별도 사건이다. run 간 memory/task/result는 공유하지 않는다. `general` 비교 조건의 Slow context는 `constraints`·`intent`로 축소해 persona 배경/선호를 전달하지 않는다.

모든 실제 AI 실행은 Slow를 활성화한다. 기존 `enable_slow_loop` 설정 필드는 이전 study 파일 호환용으로 받아들이며 입력값과 무관하게 `true`로 정규화한다. 요청/토큰 한도 기본값은 `null`(무제한)이다.

#45 Wonder는 기본 활성화다. 실제 시작한 reflection/plan_review 작업마다 한 번 0.01을 추첨하며, `wonder_seed` 또는 실행 기록의 seed로 추첨을 재현한다. 당첨된 별도 비동기 요청은 persona의 배경·디지털 친숙도·선호·제약만 받으며 `intent`·과업·현재 화면·기억·평가 정답을 받지 않는다. 일반 AI 조건에는 공통 제약만 전달한다. `wonder_draws.jsonl`은 당첨되지 않은 추첨도 기록한다. 당첨 작업의 상태는 `brain_tasks.jsonl`, 생성 결과와 기억 출처는 `brain_stages.jsonl`·`memory.jsonl`에 남긴다. 출력은 생성된 가정이며 Fast 단계 경계의 우선 삽입 대상이 아니다. 1%는 인간 행동 확률이 아니다.

요청 수와 총토큰 예산은 기본 `null`로 제한하지 않는다. 양의 정수를 지정하면 기존 예산 검사를 적용한다. 실행 시간·최대 행동 단계·요청별 출력 토큰 상한은 별도로 유지한다.

#46에서 `run.json`의 `model_routes`는 설정된 단계별 제공자/모델 경로이고, `llm_calls.jsonl`의 `provider`·`model`은 각 실제 호출의 응답 또는 시도 대상이다. Jev의 `decision_choice`는 TypeSafe `jev-latest`, perception·plan·decision fallback·reflection·plan_review·Wonder는 선택한 Gemini 모델이다. 실패·취소·재시도 시도도 별도 호출 행으로 남긴다. 비용 단가/사용량을 알 수 없는 행과 이를 포함한 실행 총비용은 `null`이다. `summary.json`의 `budget`에는 요청·토큰 사용량, 설정 한도, 마지막 한도 초과 종류(`request_limit` 또는 `token_limit`)를 기록한다. `limits`에는 행동·실행 시간 상한을 기록한다. 예산 때문에 실행하지 못한 단계는 `steps.jsonl`의 `error.budget_reason`으로 구분한다.

#47 실행 상세는 `brain_stages.jsonl`, `brain_tasks.jsonl`, `memory.jsonl`, `memory_changes.jsonl`의 원본 사건을 그대로 보존하고, 행동의 `observation_id`로 묶은 `trace`를 덧붙인다. 관찰 ID가 없는 Wonder는 `wonder_draws.jsonl`의 부모 작업 ID로 연결한다. 원본 기억이 활성 목록에서 제거돼도 ID·본문·제거 사건을 조회한다. 단계는 AI 생성물, `steps.action/result`는 제안과 도구 실행, `steps.evaluation`은 독립 평가다. 생성 단계나 Slow 완료를 과업 성공·사람의 생각으로 해석하지 않는다. 이전 실행에서 파일이 없거나 `action/result=null`이면 해당 근거를 빈 목록 또는 미확인 값으로 읽는다. CSV의 기존 카드 열 뒤에 `record_type` 등 근거 열을 추가한다.

Jev는 TypeSafe·Gemini 키가 모두 있어야 실행하며, embedding은 현재 mock/OpenAI에서만 제공한다. 미지원 조합은 run 폴더와 비교 세션 생성 전에 거부한다. 일반 AI 비교 조건에는 독립 실행별 기억을 사용하고, Fast/Slow 생성 입력의 persona 배경·선호·숙련도를 제외한다. Wonder에는 일반 조건 공통 제약만 전달한다.

생성된 단계 기록은 `content_status=generated`만 허용한다. 행동 결정의 `action`/`finish`는 제안이며 실행 결과는 기존 `ActionResult`, 성공 판정은 evaluator, 사람 검토는 별도 기록이다. 기존 `steps.jsonl`·`memory.jsonl` 소비자는 새 선택 필드와 구버전 누락 필드를 허용한다. 출처 ID의 실제 존재 확인과 작업 상태 전이 검사는 이후 조율 코드에서 수행한다.

#44 runner에서는 `observe()`의 JSON/PNG 저장과 registry 발행 뒤 Brain을 호출한다. 실제 행동 차례에는 `decision`의 제안, `action`·`result`의 실행, 새 `next_observation_id`, `evaluation`·`verification`의 독립 판정을 단계별로 기록한다. `finish`/`give_up`은 `action`·`result`가 null이고 현재 화면의 평가 결과를 별도로 기록한다. 평가하지 못한 모델·예산·시간 오류는 `unknown`이며, 행동 뒤 관찰 실패는 실행 결과를 보존하고 `post_observation_error`와 `unknown`을 남긴다. 초기 화면의 성공 조건은 Brain 전에 실행을 종료시키지 않는다.

대시보드의 일괄·비교 실행 중지는 취소 요청 파일을 통해 전달한다. 상태는 `running` → `stopping` → `cancelled`로 바뀌며, runner는 진행 중인 행동과 후속 관찰·평가를 단계 기록에 남기고 `termination_reason=cancelled`로 끝낸다. 이후 세션은 `not_started`로 남는다. 협력적 중지는 행동 timeout까지 지연될 수 있다.

## 세션

실행 전에 experiment_id, session_id, task_id, condition(general/persona), 구매 제약, persona_id(일반 조건은 없음), environment_id, site_version, model/provider/prompt_version, 예산·반복 수·예정 상태를 확정한다. 성공·실패·미확인은 평가 결과이고, timeout/error/blocked/cancelled/not_started는 종료·실행 상태다. 두 축을 혼합하지 않는다.

성공률 = 독립적으로 확인된 성공 / 사전 등록 평가 세션. 실패·오류·차단·취소·미실행·미확인 개수를 함께 공개하고 계획서의 분모를 유지한다. 모델 완료 선언은 별도 필드로 보존한다. 사이트/모델/환경 조건이 달라진 실행은 같은 비교 블록으로 묶지 않는다.

## 행동과 근거

각 시도는 session/step/action/observation ID, 전후 URL·PNG·시각, 행동 입력, 실행 결과·오류 코드, 평가 결과를 연결한다. 미실행 모델 오류/종료 선언은 action/result가 null일 수 있다. 로그 소비자는 null을 처리해야 한다.

기록 확보율 = 필수 근거가 모두 있는 행동 / 시도 행동. 부족한 항목과 건수를 표시한다. 비용 unknown은 0으로 계산하지 않는다. 실제 클릭 수와 전체 행동 수를 구분한다.

## 기능 점검

API 없는 시나리오는 `provider=scenario`, `execution_mode=scripted`, `condition=scenario`이며 `source_kind=synthetic_fixture/live_configured`로 출처를 분리한다. LLM 요청/토큰/모델은 사용하지 않는다. 코드 판정 checkpoint마다 `task_id`, `step_id`, `observation_id`, `evaluation_method=code`, `reason`, 실제 evidence를 연결한다. 성공은 등록된 체크 범위만 뜻한다. 이 데이터는 일반 AI/페르소나 AI 효과 비교의 분모에 섞지 않는다.

공개 부분 프로필은 `partial=true`, `scope=visible_cards/detail_name_price`, `unchecked_fields`로 미검증 범위를 보존한다. `search_results`는 URL과 표시 이름만 확인하므로 입력/폼 제출 성공이 아니다. `filters_price`는 URL 상한과 표시 가격, `detail_basic`은 이름/가격만 확인한다. DOM 값의 누락·서로 다른 중복 값은 unknown이며 넓은 상세 필드 성공으로 바꾸지 않는다.

키보드는 Enter/Escape/Tab/ArrowUp/ArrowDown/Space, scroll은 명시적 허용 후 ±900px이다. 신뢰된 시나리오 selector도 최신 관찰 registry에 들어 있는 목표에만 적용한다. 이동·스크롤 후에는 새 관찰을 발행하고 stale 목표를 거절한다. native select는 관찰한 옵션 값만 허용하며 custom combobox를 native select로 간주하지 않는다.

feature_id, scenario_id, 시작 상태, 입력, expected_result, 판정 방법(code/AI-assisted/human), 결과(pass/fail/unknown/unsupported), evidence를 가진다. 검색·필터·정렬은 실행 전 정의한 조건으로 확인한다. AI 해석만 있는 판정은 확정 결과로 둔갑시키지 않는다.

## 오류 복구

사전에 recoverable 오류 코드를 정한다. 같은 오류가 계속되는 동안 하나의 사건으로 묶고 정상 상태에 복귀하면 닫는다. 예비 기본안은 3회 후속 행동 내 복귀이며 본 실험 전 고정한다. 복구 여부·추가 행동·시간·최종 과업 성공을 구분한다. 정상 정책 차단은 도구 실패로 세지 않는다.

## 문제 카드와 사람 검토

scripted 실행의 실패 체크는 `classification=unmet_checkpoint`, 행동/관찰 오류는 `system_error_candidate`로 기록한다. checkpoint에 연결된 단계와 원래 evidence를 보존하고 스크립트 반복 행동을 AI 혼란으로 분류하지 않는다. 제안·완료 조건은 과업별이며 사람 검토 전이다.

카드에는 ID, task/feature/environment/site_version, 관찰 사실, 원인 가설/대안 설명, 영향 세션/해당 세션, 근거 step, 분류, 심각도, 개선 제안, 완료 조건, 회귀 검사, 독립 reviewer 2명 판정, 합의, 재검증을 둔다.

분류: UX 후보 / 실제 UX 문제 / 오탐 / 판단 보류 / 도구 오류 / 환경 오류 / 중복. 미검토 후보와 사람 확정 문제는 따로 표시한다. 중복 병합에도 원래 근거와 최초 판정을 보존한다. AI confidence를 실제 문제 확률로 설명하지 않는다.

출력: HTML 요약·개선 Markdown·CSV/JSON. 소스 연결이 없으면 파일/라인을 추정하지 않는다. 키·토큰·인증상태·개인정보를 내보내지 않는다. 동일 카드 데이터로 UI와 내보내기를 생성한다.

## 설정 추천 계약

`StudyConfig.provider_model`은 선택적 모델 override다. 명시적 선택은 model_catalog의 호환 목록으로 검증하며 legacy OpenAI config.model은 override가 없으면 유지한다. 선택 모델은 연결 검증·실행 snapshot·호출·summary에 전달한다. `/api/setup-guide/options`는 공식 발급 정보와 로컬 예시를 제공하고 `/api/setup-guide`는 provider/model/message/context/history를 받는다. 응답 source는 template 또는 ai이며 answer/personas/task_suggestion/usage를 포함한다. 추천에는 평가 정답·DOM selector를 넣지 않으며 서버/브라우저 메모리 외에 대화를 기록하지 않는다. Jev 언어 추천은 선택한 Gemini fallback으로 수행한다.
