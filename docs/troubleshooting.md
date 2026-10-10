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

## 2026-10-11 API 없는 과업 점검

- 증상: 화면 밖 가격 popup의 Max 입력을 selector로 찾아도 관찰 후보가 없어 실패했다. 원인: registry는 viewport의 최신 목표만 포함한다. 해결: 가격 메뉴 후 명시적 scroll → 재관찰 → 두 번째 가격 입력을 선택하는 live 시나리오로 제한했다. 회귀: 전역 selector로 관찰을 우회하지 않기, stale ID·허용 origin·password 차단과 Min/Max 순서 확인. 실제 결과: 지정 검색 결과부터 가격/상세 부분 실행은 성공, 전체 결과는 verification.md에 기록한다.
- 증상: 홈페이지 한글 검색 입력·Enter 후 URL 검색어를 확인하지 못했다. 원인: 한글 순차 입력과 검색 제안/제출 이벤트의 실제 원인은 아직 확정하지 못했다. 대응: `input_mode=sequential`과 한정된 키·대기를 제공하고 검색 결과 URL부터 시작하는 부분 과업을 별도로 정의했다. 회귀: 검색 결과 URL 성공을 폼 제출 성공으로 바꾸지 않기. 실제 결과: 홈페이지 제출 시도는 unknown; 해결 완료로 표시하지 않는다.
- 증상: scripted 실행의 반복 조작을 AI 혼란 후보로 해석하거나 필터 실패 카드를 마지막 단계에 연결할 수 있었다. 원인: 기존 AI 기록 해석과 최종 상태 가정을 시나리오에 적용했다. 해결: checkpoint별 단계·observation·판정 근거와 과업별 제안을 연결하고 실행 오류를 별도 후보로 구분한다. 회귀: null action/result 체크, 정상 스크립트의 반복 클릭, 실패 체크 단계와 카드 근거 일치. 실제 검사 목록과 결과는 verification.md를 따른다.

## 단일 실행 흐름과 Claude (PR 작업)

- 생성 실패·중지 후 테스트가 추가로 시작되지 않게 상태와 job ID를 확인한다. 위저드 이전/다음과 polling에도 입력을 보존한다.
- Jev는 TypeSafe+Gemini, Claude는 ANTHROPIC_API_KEY가 필요하다. 키는 서버 메모리에만 보관하고 실패 시 이전 값으로 복원한다.
- Claude 실제 FastLoop 호출이 mock으로 집계되는 것을 실패 테스트로 확인하고 Claude로 분류했다. 비용 미확인은 0원으로 바꾸지 않는다.
- 모델명 검색 안내와 실제 검색 대상의 불일치를 재현하고 run.model을 포함했다. 14개 기록/결과 필터/모델명 검색을 브라우저로 검사한다.
- 성공 조건의 간단한 완료 문구는 body text_contains 확인이다. 실제 과업 전체를 증명하는 일반 평가기로 해석하지 않는다.


## 마지막 checkpoint가 실행 시간 상한 뒤 성공한 문제 (2026-10-11)

- 증상: 3초 제한인데 마지막 코드 검사가 4초 뒤 pass를 반환하면 scenario_completed/success가 됐다.
- 원인: 단계 시작 전만 deadline을 확인해 await 중 소요 시간을 제한하지 못했다.
- 해결: 남은 시간의 asyncio.timeout으로 브라우저 작업 전체를 제한하고 timeout은 unknown으로 기록한다. 중간 action/result와 관찰 ID를 보존하고 초기 진입 중 중단된 브라우저를 정리한다.
- 함께 확인할 회귀: 수동 검사·행동 후 검사·실행 중 timeout·브라우저 시작 중 timeout, 기존 정상 합성 실행.
- 실제 검증: 위 timeout 회귀 4개 통과, 재리뷰에서 중요 미해결 결함 없음. 전체 결과는 verification.md 참고.
