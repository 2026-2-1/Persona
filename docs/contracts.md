# 평가·기록·결과 계약

이 문서의 새 필드는 목표 계약이다. 현재 schemas.py에 모두 존재하지 않는다. 구현 이슈에서 schema_version과 읽기 호환성을 추가한다.

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
