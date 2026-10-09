# 트러블슈팅과 회귀 확인

기존 테스트가 보호하는 사례다. 변경할 때 원래 증상과 함께 발생한 문제를 확인한다.

| 영역·증상 | 확인할 원인/회귀 | 기존 테스트 |
|---|---|---|
| 이동된 dashboard study가 persona를 못 찾음 | config-relative/절대 경로; 작업 snapshot | test_batch_snapshot_resolves_persona_after_relocation |
| 새 persona에 과거 run이 붙음 | generation/study ID 분리; 입력 배경·과제 보존 | test_generation_uses_form_input_and_avoids_unrelated_old_run |
| 최신 화면이 안 보임 | step 연결 전 observation, 중첩 runs 검색 | test_latest_observation_and_nested_run_are_visible |
| 실패를 완료로 표시 | subprocess 결과와 run 종료 사유 전달 | test_batch_reports_browser_failure_instead_of_completion |
| 실패 로그에 키 노출 | 서버 오류 메시지에서 값 제거; API 상태에 내부 필드 제외 | test_failed_job_explains_error_without_exposing_key |
| 잘못된 대상/외부 이동 | 최신 observation만 허용; 허용 origin 검사 | test_observation_hides_hidden_text_and_stale_ids_are_rejected |
| 잘못된 모델 완료/무한 반복 | 독립 evaluator; 같은 상태 행동 반복 종료 | test_runner_distinguishes_false_finish_and_repeated_state |
| 한도 초과 추가 요청 | reserve/settle 공통 예산 | test_mock_run_stops_when_request_budget_is_exhausted |

## 아직 검증/수정할 후보

- select 옵션 후보 ID 중복: 옵션별 ID를 분리하고 Jev/Gemini 매핑·옵션 순서를 검증한다.
- task 전체를 입력 후보 값으로 사용: 실제 검색어 생성 계약을 추가하고 기존 mock 단계 인식을 유지한다.
- review의 result=null 경로: 종료 선언·모델 오류 로그를 넣어 결과·설문이 정상 생성되는지 검증한다.
- Windows 저장/읽기 인코딩: 한글 fixture·로그·문서를 UTF-8로 읽고 쓰는지 실제 실행으로 확인한다.

새 기록은 날짜/이슈/증상/재현/원인/최소 수정/함께 확인한 회귀/실제 결과를 남긴다. 확인되지 않은 후보를 확정 버그나 해결 완료로 쓰지 않는다.

## 2026-10-09 안정화와 최종 리뷰

- select 옵션 ID 충돌을 회귀 테스트로 재현(실패)하고 옵션 인덱스로 분리해 통과했다. 다른 옵션 선택이 첫 옵션으로 잘못 매핑되지 않는지 검사했다.
- null action/result에서 review가 예외를 내는 것을 재현하고 종료 선언을 반복 행동 후보에서 제외했다. 반복 근거에는 행동 종류와 대상 모두 일치하는 단계만 연결했다.
- Jev 검색 입력은 전체 과제 문장 대신 생성 모델이 실제 입력값을 만든다. 빈 입력과 잘못된 기존 입력 교체를 각각 검증했다.
- 일반 AI 비교에는 배경/선호를 프롬프트와 persona artifact에 넣지 않는다. 구매 제약과 과업 의도만 보존한다.
- post-action 관찰 실패 시 실행한 행동이 로그에서 사라지는 것을 재현하고 부분 로그와 실제 시도 분모를 보존했다. 이전 정상 행동만으로 기록 확보율 100%를 표시하지 않게 했다.
- 비교 세션 run ID를 시작 전에 확정해 실행 중/중지 후에도 원자료와 연결한다. 일반 조건의 표시와 rich persona 노출을 분리했다.
- 중첩 experiments 폴더의 비교 데이터 누락을 재현하고 안전한 runs 하위 전체 검색으로 수정했다.

각 사례는 tests/test_regressions.py, test_metrics.py, test_experiments.py, test_dashboard_mvp.py로 보호한다. 실제 실행 결과는 verification.md에 기록한다.
