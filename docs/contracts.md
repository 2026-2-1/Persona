# 평가·기록·결과 계약

이 문서의 일부 필드는 목표 계약이며 실행 코드에 아직 연결되지 않았다. [#39](https://github.com/2026-2-1/Persona/issues/39)의 기록 스키마와 실제 구현 상태는 아래를 따른다.

## Brain 기록 계약 (#39)

| 기록 | 버전·내용 | 현재 생성 여부 |
|---|---|---|
| `BrainStageRecord` | 1.0; 생성된 importance/perception/plan/decision/reflection/plan_review/wonder, 관찰·계획 버전·참조 기억과 시간 | importance 결과만 `brain_stages.jsonl`에 기록; 나머지는 후속 이슈 |
| `BrainTaskEvent` | 1.0; 실제 비동기 작업의 예약·시작·생략·완료·실패·취소 사건과 snapshot 출처 | importance 작업만 `brain_tasks.jsonl`에 기록; 나머지는 후속 이슈 |
| `MemoryEntry` | 구버전 입력은 1.0으로 읽음. 새 기록은 2.0이며 생성 단계·원본 기억 ID를 선택적으로 연결 | `MemoryStore`가 2.0 기록 생성 |
| `MemoryChangeEvent` | 1.0; 중요도 점수 갱신 또는 활성 메모리 제거의 원본 ID·점수·사유 | 제거·중요도 갱신 사건을 `memory_changes.jsonl`에 기록 |

`StudyConfig.max_active_memories`는 기본 64, 허용 범위 10~64다. 활성 기억의 최근 10개를 보호하고, 나머지는 중요도 우선·동점일 때 생성 순번이 최신인 순서로 남긴다. `memory_limit`은 별도의 검색 반환 개수다. 원본 `memory.jsonl`은 제거·점수 갱신 시에도 보존하고, 제거 ID·사유·보존 점수 또는 1~10점 갱신은 `memory_changes.jsonl`에 기록한다. 중요도 미산정은 `null`이다. 구버전 `MemoryEntry` 1.0의 중요도는 0~5로 읽고, 새 2.0 기록과 `MemoryChangeEvent`의 중요도는 논문 Appendix C.7을 따라 1~10으로 제한한다. 현재 검색은 I/Q/R을 같은 가중치로 합치며 없는 요소는 합산에서 제외한다. Fast/Slow별 가중치 보완은 #54다. 현재 Runner는 행동 뒤 저장한 observation/plan/action 기억을 별도 비동기 중요도 LLM 작업으로 점수화한다. 점수 반영이 끝나기 전에는 기존 미산정 상태로 검색한다.

요청 수와 총토큰 예산은 기본 `null`로 제한하지 않는다. 양의 정수를 지정하면 기존 예산 검사를 적용한다. 실행 시간·최대 행동 단계·요청별 출력 토큰 상한은 별도로 유지한다.

생성된 단계 기록은 `content_status=generated`만 허용한다. 행동 결정의 `action`/`finish`는 제안이며 실행 결과는 기존 `ActionResult`, 성공 판정은 evaluator, 사람 검토는 별도 기록이다. 기존 `steps.jsonl`·`memory.jsonl` 소비자는 새 선택 필드와 구버전 누락 필드를 허용한다. 출처 ID의 실제 존재 확인과 작업 상태 전이 검사는 이후 조율 코드에서 수행한다.

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

## C/P05 구현 계약 (2026-10-11)

`CandidateReviewInput`은 card_id(기존 issue_id), card_version(SHA256), reviewer_id(로컬 별칭), verdict, note를 받는다. 서버의 `CandidateReviewRecord`는 schema_version=1.0, UUID review_id, run_id, UTC created_at을 추가한다. 클라이언트는 실행 ID·시각을 요청 본문에 임의 지정할 수 없다.

판정은 valid(유효 후보)/invalid(무효 후보)/deferred(보류)/tool_error(도구 오류)/environment_error(환경 오류)다. 후보 유효 판정은 독립 과업 성공이나 확정 UX 결함을 뜻하지 않는다. 상세 기준은 A 담당이 합의한다. 미검토는 저장할 판정 값이 아니라 needs_human_review 상태다.

카드 식별은 run_id+card_id+card_version이다. 카드 관찰·가설·제안·근거 행동 내용이 바뀌면 새 버전이며 검토 이력·판정·시각은 버전에 포함하지 않는다. 이전 버전 기록은 보존하되 현재 카드에 자동 적용하지 않는다. 출처 metadata execution_mode/source_kind는 기존 실행값을 전달하고 과거 누락은 unknown이다. [가상 계약 예시](examples/c-review-contract.json)는 실제 API/사이트 검증 결과가 아니다.

## C/P06 저장·조회 API

`GET /api/reviews/<run_id>`는 `{run_id, reviews, cards, review_summary}`를 제공한다. `POST` 같은 경로에 CandidateReviewInput을 보내면 서버가 생성한 CandidateReviewRecord를 201로 반환한다. 실행 상세에도 reviews와 review_summary를 추가한다. 기존 출력/카드/verification 필드는 유지한다.

카드의 review_history는 현재 card_version과 일치하는 판정만 포함한다. latest_review는 그중 마지막 저장 판정이며 미검토는 null이다. 과거 버전 판정은 전체 reviews에 남는다. 상태는 needs_human_review/reviewed/deferred이며 verdict와 과업 verification은 별도 필드다. review_summary의 reviewed는 보류 제외 판정 완료 건수, deferred는 보류 건수, unreviewed는 현재 버전 미검토 건수다.

검토자 별칭은 인증된 사용자 신원이나 독립 2인 합의를 의미하지 않는다. 이전 판정을 덮어쓰지 않고 실행 하위 candidate_reviews.jsonl에 저장한다. 메모에는 키·인증 URL·개인정보를 넣지 않는다. 손상된 이력은 미검토로 조용히 초기화하지 않고 오류로 드러내며, 저장 전 백업·복구가 필요하다. 로컬 단일 서버 사용 범위이며 다중 프로세스 동시 쓰기는 지원하지 않는다.

## C/P08 집계 계약

비교는 general/persona 예정 세션을 분모로 유지하며 명시적인 execution_mode=scripted 또는 provider=scenario는 배제한다. 독립 결과 success/failure/unknown과 실행 statuses는 두 축이다. rate는 세션이 없을 때 null, 예정 세션에 성공이 없으면 0이다. median_actions/median_ms는 성공 세션의 측정 가능한 값만 사용하며 대응쌍 변화량이 아니다. 실제 대상 수는 median_actions_sessions/median_ms_sessions로 제공한다.

cost, llm_request_count, llm_tokens, input_tokens, output_tokens는 전체 대상의 값이 알려져 있을 때만 합계를 제공한다. 각 필드에 `_known_total`, `_known_sessions`, `_unknown_sessions`를 추가해 알려진 부분 합계와 누락을 보여준다. 알려진 값이 전혀 없으면 부분 합계도 null, 실제 알려진 0은 0이다. provider_usage는 같은 coverage 필드를 제공자별로 제공한다. 빈 usage와 비영 요청 수가 충돌하면 토큰을 0으로 추정하지 않는다.

recording.complete/attempted와 rate는 전체 범위가 알려져 있을 때 제공한다. known_total/known_sessions/unknown_sessions와 known_rate는 확인된 범위만의 합계·비율이며 전체 기록 확보율로 바꿔 표시하지 않는다. 기존 실험 JSON은 조회 시 현재 집계를 계산하되 파일이나 예정 세션을 고치지 않는다. 예전 기록에 없는 측정값은 unknown이다.

### 실제 호출 측정과 예산 계수 구분

새 실행은 llm_tokens_complete/llm_tokens_measured_total/llm_tokens_known_calls/llm_tokens_unknown_calls와 cost_complete/cost_measured_total/provider_usage_complete를 저장한다. provider_usage는 요청·입력·출력·추정비용 각각 complete/measured_total과 토큰 known_calls/unknown_calls를 제공한다. 알려진 일부 입력만 있고 출력이 없으면 입력 측정값은 보존하되 전체 토큰은 미확인이다. 요청 수보다 호출 기록이 적으면 제공자별 전체 요청/사용량/비용을 확인됐다고 처리하지 않는다.

기존 summary.llm_tokens 예산 계수와 provider의 기존 합산 필드는 호환 목적으로 유지한다. 제한 검사는 기존 BudgetManager를 사용하고 실제 집계는 completeness와 측정값을 우선한다. 따라서 group의 known_total은 완전한 세션 외에 확인된 호출의 부분 합계도 포함할 수 있고 known_sessions는 완전한 측정 세션 수다. 과거 completeness 없는 값은 제공된 수치로 호환 조회되며 정확한 호출 측정인지 사후 재구성할 수 없다는 제한을 가진다.

## D 조회 상태와 새 AI 출처 (2026-10-15 작업 브랜치)

상세 조회 실패는 정상 빈 후보와 다르다. 마지막 정상 상세를 보존할 때 실패와 시각을 표시하고 최신 조회가 회복될 때까지 저장·내보내기를 제공하지 않는다. 새 AI 실행은 execution_mode=ai를 기록하며 StudyConfig.source_kind는 unknown/synthetic_fixture/live_configured다. 내장 shop fixture만 알려진 synthetic_fixture로 기록한다. legacy 출처는 추정하지 않는다. 복구 null rate는 미확인, 명시적 episodes=[]는 대상 사건 없음으로 구분한다.

## Brain 소비와 내보내기 (D #47 작업 브랜치)

run_detail.brain은 stages/task_events/tasks/task_counts/memories/memory_changes/warnings를 제공한다. 작업별 마지막 append 상태와 전체 사건을 구분하고 원본 기억+변경 사건을 읽기 전용 overlay한다. Brain 없는 legacy CSV는 기존 열을 유지하고 Brain CSV는 record_type/record_id/brain_record 추가 열 및 타입별 행을 가진다. 생성물과 후보/독립 평가/사람 검토를 합산하지 않는다. [상세](tasks/d-brain-trace-viewer.md).
