# 검증 기록

## 2026-10-16 최신 Brain + D/C 통합 (#69/#47/#36)

- `codex/latest-pr-integration-20261015`에 #79 고정 head `1f82379b0139`, 별도 분기된 #78 `28f912b90a7f` 및 #75 `9c397b4f94e1` 후속을 통합했다. D #68/C 측정/문서 #80을 보존했다. [통합 범위·재현·한계](handoffs/2026-10-16-latest-pr-integration.md)를 따른다.
- 최신 Fast kind·adopted/discarded·Wonder와 검증 reader/별칭의 불일치를 전용 3개 실패 테스트, 채택 배지 누락을 390px 브라우저 실패로 먼저 재현했다. reader/단일 패널/타입별 출력을 통일한 뒤 통과했다.
- 전체 pytest: 처음 402 passed/1 failed(기존 #75 중복 패널 제목), 통합 패널에 맞춰 생성/실행/독립 결과 회귀를 보존한 최종 **403 passed in 168.98s**. 이후 #75의 데이터 갱신 대기 1줄을 별도 merge하고 해당 Chromium 검사 **1 passed in 3.51s**. #78 초기화 관련 2개도 통과했다.
- doctor: Python 3.13.13, Chromium available, study_errors 없음. Node 문법, Python compileall, repo/staged 검사와 diff 공백 검사 통과. 원격 CI는 통합 PR의 현재 head 검사로 확인한다.
- 실제 무료 Mock `20261015T145603-83f78314`: 6행동·60요청·독립 verified_success, 생성 60·작업 사건 193·기억 30·Wonder 추첨 12/당첨 1·읽기 경고 0. 최신 상태 completed 47/adopted 6/discarded 7. plan_review는 stale 5 + 종료 미소비 1로 전부 폐기됐고 reflection 5/Wonder 1이 채택됐다. 실제 계획의 출처 관찰 `obs-3fda456cc3`을 화면에서 열었다.
- 실제 scripted 합성 필터 결함 `20261015T145630-7a949075`: 후보 `feature-6-filters`의 행동 6 이미지 확인 → deferred 초안 입력 → 다른 실행 왕복/자동 갱신 유지 → 저장 → 새로고침 → 이력 1건 유지. 독립 failure는 변하지 않았다.
- 두 실행의 JSON/CSV/Markdown/HTML을 저장해 상세 API와 전체 Brain/카드 ID·버전·판정·메모를 대조했다. Brain CSV 330행의 타입별 JSON과 step trace도 일치했다. 실제 인앱 JSON 다운로드는 확인했고 나머지 실제 형식은 응답을 대조했다. 자동 Chromium 회귀에서는 네 형식 모두 다운로드했다. 인앱 다운로드 도구의 긴 지연과 검증 방법을 인수인계에 명시했다.
- 유료 API·실제 사이트·사람 판단 유사성·기업 데이터는 이 검증에 사용하지 않았다. B #58/#60/#62와 prototype/main 병합은 별도다. 결과/스크린샷/원자료는 로컬 ignored/임시 폴더에 유지했다.

## 2026-10-15 23:27 KST 최신 원격 구현 반영 정정

- 직접 GitHub PR/이슈 목록과 prototype SHA를 다시 조회하고 #66/#71~#79 본문·고정 head, #79의 Brain/Runner/Slow/Memory/Schema/비교 코드를 읽었다. #78/#79의 분기와 #78 후속 패치도 확인했다. [최신 확인 기록](handoffs/2026-10-15-latest-github-review.md)에 근거를 남겼다.
- 실험/회의/제출 문서의 preview 미포함과 최신 PR 구현 포함을 구분했다. 강제 Slow 활성, 점수화 결합, 현재 검색 profile, 동일 계획 검토 채택, 8상태/D 소비 중복, 분기된 후속 수정이 연구·통합 안건에 반영됐다.
- 실제 검사: repository check PASS(0 problems), 관련 문서 6개 링크/표/펜스/문자 검사 PASS, git diff --check PASS. 새 원격 기능을 통합하거나 pytest/Mock/브라우저/유료 API를 새로 실행한 것은 아니다.

## 2026-10-15 연구·회의·제출 문서 정리

- 사용자 제공 팀 대화와 미수령 확인을 반영해 Slow 실행 빈도→검색 정책 실험 계획, 회의 안건/결정표, 기업 데이터·시스템 구조·Novelty 제출 초안을 작성했다. 기업체 자료 확보 수량은 0건이며 요청 목표·18/90/216세션은 제안으로 구분했다.
- 원문 조사로 기존 구조·성찰 비교·버전 검증 선행과 기여 후보를 별도 기록했다. 연구 신규성과 인간 재현성을 확정하지 않았다.
- 기존 메모리 계획은 2차 상세로 연결하고 현재 상태·Brain 생성 기록 계약의 오래된 표현을 preview에 맞게 정정했다. 실행 코드·스키마 변경은 없다.
- 실제 수행: repository check PASS(0 problems), 새/관련 연구 문서 5개의 로컬 링크·표 열 수·코드 펜스 검사 PASS, git diff --check PASS, 문서 커밋 전 staged 검사 PASS.
- 문서 변경이므로 pytest·Mock·유료 API·기업/사람 실험을 새로 실행하지 않았다. 324개 통과는 앞선 통합 preview의 검증 기록이며 이번 문서 작업 결과로 재사용하지 않는다.

## 2026-10-14 #40 메모리 입력 분리 첫 단계

Fast 모델 입력에서 점수 상위 기억(후보 선택 모델 4개, 생성 모델 6개)과 최근 행동 이력을 별도 필드로 전달하도록 수정했다. 변경 후 `git diff --check`와 관련 Python 파일의 `compileall`은 통과했다. pytest·실제 모델 호출·브라우저 실행은 아직 수행하지 않았다. 이 기록은 #40 전체의 완료 검증이 아니다.

## 2026-10-14 #39 Brain 기록 계약

로컬 Python 3.14에서 새 `BrainStageRecord`의 생성물·출처·계획 참조·시간대 검증 7개를 먼저 실패 재현(모델 미정의)한 뒤 통과시켰다. `python3 -m pytest -q tests/test_brain_schema.py tests/test_core.py tests/test_metrics.py`는 fixture 서버의 소켓 바인딩이 제한된 실행 환경에서 4개 실패·22개 통과였고, 소켓이 허용된 실행에서 **26개 통과**했다. `python3 scripts/check_repo.py`와 `git diff --check`도 통과했다.

후속 단계에서는 비동기 작업 사건, 메모리 변경 사건, 구버전 `MemoryEntry` 읽기, `max_active_memories` 예약 필드, 제거 후 단조 순번과 Slow 출처를 추가했다. 제거 뒤 Slow가 목록 길이를 snapshot 순번으로 쓰는 실패를 재현하고 수정했다. 양의 N을 입력해도 실제 상한이 적용되지 않는 문제를 실패 테스트로 확인한 뒤 명시적 미지원 오류로 막았다. 첫 전체 검사인 로컬 Python 3.14의 `python3 -m pytest -q`는 **197 passed in 80.46s**였다. 유료 API나 실제 외부 사이트 호출은 하지 않았다.

예약 필드의 미지원 검증을 추가한 뒤 `tests/test_brain_schema.py tests/test_core.py tests/test_dashboard.py tests/test_experiments.py` 관련 **35개가 통과**했다. `doctor --study configs/study.json`은 제한된 실행 환경에서 Chromium 권한 오류였고 허용된 환경에서 재실행한 결과 Playwright Chromium 사용 가능·설정 오류 없음이었다. `scripts/check_repo.py`와 `git diff --check`도 통과했다.

이 결과는 새 기록 스키마의 직렬화와 기존 mock/메모리·지표·대시보드·보고서 경로의 호환성 검사다. Runner가 새 Brain 단계/작업 사건을 실제로 쓰거나 두 루프가 동작한다는 검증은 아니다. 활성 N개 상한도 아직 적용하지 않는다.

이후 사용자 결정에 따라 새 메모리 중요도를 1~10으로 제한하고 구버전 1.0의 0~5점을 버전별로 읽도록 변경했다. 위 검사 수치는 이 변경 전 실행 결과이며 변경 후 검사는 아직 수행하지 않았다.

## 2026-10-09 Windows 1차 MVP

환경: Windows, Python 3.13.5, Playwright 1.55.0, Chromium 140.0.7339.16 (build 1187). 원본 e4dfa98에서 개발한 작업 트리 기준이다.

- 초기 baseline: 기존 pytest 20개 통과, doctor 오류 없음, mock 과업 6행동/6성공·verified_success.
- 최종 전체 테스트: 47 passed in 43.85s. Repository check: PASS (0 problems), staged 검사와 diff whitespace 검사 통과.
- 브라우저 검사: 4 passed in 10.23s. 메뉴 이동·입력 유지·실행 선택 유지·API 키 명시 연결/비저장·교차 origin 요청 거절·390px 모바일 overflow·미실행 근거 링크 비활성 확인.
- 비교 CLI: experiment 20261009T030843-c7571fb3, 일반 6/6 성공·페르소나 6/6 성공, system_errors 0. mock 비교이며 persona 효과를 측정한 실험이 아니다.
- 최종 리뷰의 4개 지적에 회귀 검사를 추가하고 수정했다: 기존 검색어 교체, post-action capture 누락 분모, 일반 실행 표시, 중지 세션의 사전 run ID. 미실행 ID는 실제 근거가 생기기 전 클릭하지 못하게 했다.
- 테스트에서 초기 Page.goto의 5초 제한이 한 번 초과했다. 동일 검사 단독 실행은 통과했고, 실패 유도 통합 테스트만 로컬 준비 시간을 15초로 설정한 뒤 전체 46개가 통과했다. 제품의 시간 제한은 임의 변경하지 않았다.

## 검증 범위

실제 API 키 호출, ChatGPT 구독 OAuth, 실제 데카트론의 4개 과업, 사람 검토/사용성 효과, Linux CI는 로컬 검사만으로 완료라고 판단하지 않는다. GitHub CI 결과와 마지막 통합 검사 결과는 아래에 추가한다. 인증/키 연결은 fake provider를 사용해 rollback/비노출을 검증했다.

원자료 runs/는 로컬에만 존재하고 push하지 않는다. 스크린샷의 fixture는 연구 검증용 데모다.

## 브라우저 실제 버튼 통합

기본 데모 설정 → 2명 생성 → 반복 1회 AI 비교 → 대응 세션 근거 클릭을 실제 Chromium에서 실행했다. Experiment 20261009T032000-19e8ec07: 일반 2/2·페르소나 2/2 성공, system_errors 0. 총 4세션을 예정 분모에 유지했다. API 연결과 구독 연결의 실사용 결과를 뜻하지 않는다.

## 실패 조건·내보내기와 원격 검사

- 검증용 미충족 조건을 의도적으로 등록한 fixture 실행 20261009T032454-95b9bbf3에서 실패 카드 표시와 JSON/CSV/Markdown/HTML 네 가지 HTTP 출력이 모두 정상 동작했다. 실제 발견한 사이트 결함 사례가 아니다.
- 최종 UI 변경 후 브라우저 테스트 4개 재통과. API 키 연결 실검증은 수행하지 않았다.
- GitHub 검사: https://github.com/2026-2-1/Persona/actions/runs/37879085009 (소스 커밋 e57db11). Ubuntu/Python 3.11 job 통과를 확인했다. Windows/Python 3.13 job은 이 기록 작성 당시 실행 중이며 해당 링크에서 최종 상태를 확인한다.

추가 확인: 위 e57db11 소스 기준 GitHub 검사에서 Ubuntu/Python 3.11과 Windows/Python 3.13 두 job 모두 success로 완료됐다. 이후 문서 변경 커밋은 동일 소스를 유지하며 자동 검사를 다시 실행한다.

## 2026-10-09 화면 간소화

사용자 요청으로 로컬 Pretendard Variable(-0.03em 자간), 새 SVG 심볼, 짧은 제목/작업 상태를 적용했다. 반복 연구 안내와 점으로 연결한 상태 문장을 제거했다. 기존 설정/메뉴/선택/키 비저장 회귀는 dashboard browser + MVP 검사 9개 통과. 인앱 브라우저에서 새 폰트 family와 14px 기준 자간 -0.42px, 로고 경로, 갱신된 화면을 확인했다. API/평가/비교 실행 계약은 유지한다.

로고 후속 변경: 참고 이미지의 기하학 느낌을 반영한 사각 P + ersona 벡터 워드마크와 흰색 버전, 파비콘용 P를 적용했다. 브라우저 회귀 4개 통과, 인앱 화면에서 로고 표시 확인.

이미지 로고 적용: 이미지 생성 PNG 심볼을 첫 글자 P 대신 사용하고 ersona를 연결했다. 원본 투명 알파와 전체 생성 로고를 프로젝트 assets에 보존했다. 동일 PNG 파비콘 적용, 인앱 화면 확인, 브라우저 회귀 4개 통과.

## 대시보드 단일 흐름·Claude PR

- 전체 검사: 63 passed in 43.18s. Claude fake HTTP/API 연결·rollback/비노출, 실제 FastLoop 제공자 집계, 위저드 입력 유지·키 gate·자동 생성 성공/실패 분기, 14개 기록·모델명 검색/필터·모바일을 포함한다.
- 인앱 실제 버튼: 무료 데모 → 다음 3회 → AI 비교 선택 → 비교 실행. 사용자 생성과 4세션 비교가 자동으로 이어졌다. Experiment 20261009T050944-c254441f, 일반 2/2·페르소나 2/2 성공. mock 흐름 검증이며 실행 시간 차이를 persona 효과로 해석하지 않는다.
- Claude Sonnet 4.6 Messages API 제공자를 추가했다. 실제 키 호출은 수행하지 않았으며 fake HTTP 계약으로 검증했다. Claude 비용은 미확인으로 유지한다.
- 코드 리뷰에서 모델명 검색 대상 누락을 발견해 실패 재현 후 수정했다. 상위 #6/#7/#8은 미완성 범위를 유지하고 이 작업의 하위 #13/#14/#15를 별도 완료 처리한다.


## 2026-10-11 API 없는 과업 점검 (#2 / #3)

검증 환경: Windows, Python 3.13.5, Playwright 1.55 Chromium. LLM 제공자 API 키 호출 없이 실행했다. Mock 회귀의 `complete` 호출은 로컬 모의 제공자이며 유료 API 호출이 아니다.

| 사전 정의한 합성 과업 | 실행 ID | 독립 판정 |
|---|---|---|
| 검색·색상/가격 필터·상세 | 20261010T154055-3ac4bff2 | success |
| 빈 결과·검색어 변경 | 20261010T154101-aefd008f | success |
| 필터 초기화·결과 복원 | 20261010T154105-28253f19 | success |
| 스크롤·픽업 안내 표시 | 20261010T154111-d81d66cc | success |
| 검색 결과 불일치 주입 | 20261010T154115-db985e5d | failure |
| 필터 미반영 주입 | 20261010T154202-53d0e9d7 | failure |
| 상세 누락 주입 | 20261010T154256-8954defb | failure |
| 초기화 실패 주입 | 20261010T154306-066b4f34 | failure |

위 8개 실행 모두 LLM 요청 0, 기록 확보율 100%. 합성 결함이어서 실제 사이트 결함 발견 사례가 아니다. 원자료는 Git 제외 `runs/offline-validation/`에만 보관한다.

실제 공개 사이트 실행 `20261010T153846-0c0a13c5`는 지정 `search?query=러닝화` URL부터 가격 최대 80000 적용, 상품 8926930 상세 진입까지 6개 동작을 수행했다. 표시 카드의 검색어 포함, 필터 후 표시 카드 12개 가격 <=80000, 상세 `남성 러닝화 킵코어` 79900을 확인했다. 부분 독립 판정 success, 17.134초, API 요청·토큰·비용 0, 기록 확보율 100%였다. 사이트 자체의 상품 조회 요청은 사용됐으며 LLM API 호출과 구분한다.

홈페이지 한글 검색 입력·Enter 제출 실험 `20261010T153352-0871d10a`는 입력창 `러닝화`는 확인했지만 URL 검색어가 없어 unknown으로 종료했다. 부분 결과는 제출 성공·전체 카탈로그·의미 관련성·색상·사이즈·용도·재고·픽업의 성공 증거가 아니다. 후속 확대는 [#19](https://github.com/2026-2-1/Persona/issues/19)에 기록했다.

인앱 실제 버튼: API 없는 과업 점검 → 다음 → 필터 미반영 선택 → 다음 → 다음 → 점검 실행. 사용자 생성/키 연결 없이 실행 `20261010T154423-e85c7f87` 종료, 필터 독립 failure와 카드가 생성됐다. `행동 6 근거 보기`가 최종 상세가 아니라 필터 적용 직후 화면 `obs-a7a19a85d1`로 이동하는 것을 확인했다. API 모델 호출 0회, 8개 행동·기록 확보율 100%, 8.7초였다.

리뷰에서 마지막 checkpoint가 시간 상한 뒤 success로 종료할 수 있는 문제를 재현했다. 남은 시간으로 전체 비동기 브라우저 실행을 취소하도록 수정하고, 중단 중 행동/결과를 보존하며 timeout은 unknown으로 기록한다. 행동/수동 검사/시작 중 timeout 회귀 4개를 통과했고 재리뷰에서 추가 중요 결함이 없었다.

최종 전체 pytest: **122 passed in 259.84s**. JavaScript 문법 검사, repository check(0 problems), doctor(설정 오류 없음), staged 경로/민감정보 검사와 diff 공백 검사 통과. 기존 Mock 실행 `20261010T153943-678dd2cd`는 6행동 verified_success/success, 기록 확보율100%였다. API 금지 패치 회귀와 키 없는 대시보드 job/브라우저 회귀를 포함한다. GitHub CI는 PR에서 별도 확인한다.


## 2026-10-11 오전 실제 부분 재점검·한 화면 배치

2026-10-11 09:28 KST에 실행한 `20261011T002846-0a102689`: 지정된 검색 URL/표시 이름, 최대80000 가격 필터, 킵코어 상세 이름/가격 3개 체크 pass. 상세 79900, 필터 후 표시 카드12개 상한 이내, 6개 행동 모두 성공, 21.079초, 기록100%, 모델 API0. 실행 summary와 대시보드 `/api/run/<id>`를 함께 확인했다. API 결과에서 개선 cards는 0개였다. 실패/오류가 없으므로 문제 카드를 임의 생성하지 않았다.

검색 폼 제출·재고·픽업·전체 사이트 사용성은 이 결과로 검증되지 않는다. 원자료는 runs/live-check에만 보관한다. 인앱 탭은 이전 연결 오류의 data URL에 머물러 브라우저 정책상 직접 제어하지 않았다. UI 검증은 독립 로컬 dashboard browser 회귀로 수행하며 실제 실행/카드 확인은 제공 API 응답으로 수행한다.

화면 검증은 내용이 비어 있는 시점이 아니라 세 판정과 성공 상태가 로드된 뒤 높이를 측정한다. 완료 job 배너가 남아 공간을 차지하는 회귀도 실패 재현 후 숨김 처리했고, 진행 중 배너/중지 접근은 유지한다.

최종 전체 pytest: **124 passed in 353.51s**. 1365×768 및 1280×720에서 세 판정 로드 후 완료 배너 숨김/페이지 높이, 진행 중 중지 접근, 실패 후 새로고침 시 안내 유지, 내보내기 접근을 포함한다. 기존 Mock 실행 `20261011T003722-1b102b4d`는 6행동 verified_success/success였다. JS 문법·repo/staged 경로/민감정보·공백 검사 통과. 리뷰의 실패 안내 숨김 문제를 재현·수정하고 재리뷰에서 추가 중요 결함은 없었다. 원격 검사는 PR에서 별도로 기록한다.


## 2026-10-11 점검 상태 체크리스트 (#23)

항목/상태 배지가 떨어져 보이던 표시를 아이콘·항목·상태·펼침 한 행으로 정리했다. 판정 데이터와 평가기/개선 카드 데이터는 바꾸지 않았다. 통과·실패·미확인 구분, 근거 내용, polling 뒤 펼침 유지와 실행 변경 초기화를 확인했다. 키보드 초점 테두리의 바깥 잘림을 2px+4px offset으로 재현한 뒤 안쪽 offset으로 수정해 검증했다. 이미지 예시는 독립 로컬 테스트의 합성 데이터다.

최종 전체 pytest: **125 passed in 601.70s**. JS 문법·repo/staged 경로/민감정보·공백 검사 통과. 기존 desktop 높이·모바일·위저드·키 비저장·검색 회귀를 포함한다. 코드 리뷰의 중요 초점 표시 지적을 수정했다. 원격 CI는 PR에서 별도로 기록한다.

## 2026-10-11 설정 도우미 / #25

- 전체 pytest: 184 passed (190.34s). 최종 UI 상태 문구 변경을 포함한 focused 브라우저·도우미·HTTP·모델 검사 71 passed (100.10s). 독립 리뷰의 지적 3건 수정 후 병합 차단 사항 없음.
- doctor: Python 3.13.5 / Playwright 1.55.0 Chromium / study_errors 없음.
- mock 통합: verified_success, 검색·필터·상세 pass, 6행동 / 기록 6건. 실제 LLM 호출 없음.
- node --check / git diff --check / repository check: 통과.
- 1365×768 실제 로컬 화면 캡처: 두 열·가로 넘침 없음. 유료 연결/추천은 fake 응답으로 테스트하며 실제 API 계정 지원이나 과금은 미검증이다.
- 추천은 source template/ai를 구분하고 사용자가 적용해야 사용자 설명을 바꾼다. 키·인증 URL·Unicode 이스케이프 응답 우회와 요청/토큰 한도를 재현 검사한다.

최종 화면 확인에서 초기 상태 로딩과 도우미 이동의 경합을 발견해 실패 테스트로 재현 후 수정했다. 브라우저 회귀 17 passed (249.58s). 모델 발급 안내 간격도 줄였다. 앞선 커밋의 Windows/Ubuntu CI는 모두 통과했다.

## 2026-10-11 C/P05·P06

- Baseline reports/metrics/experiments 10 passed.
- P05 계약·보고서 집중25 passed; 한글/긴 카드 ID와 동일 observation ID의 내용 변경 회귀를 포함한다. 구현자 시나리오/회귀 포함38 passed, 작업 리뷰 지적2건 수정 후 blocker 없음.
- P06 새 저장/HTTP/출력·계약·UI 집중37 passed. 보안 보완 후 candidate_reviews/setup_guide/HTTP 68 passed. 따옴표·역슬래시·개행 환경 비밀값 우회9건 실패 재현 후 통과했다.
- 합성 필터 결함 scenario 실제 실행 ID `20261011T105939-438c89d8`: failure, 검색/상세 pass·필터 fail, 8행동/기록8, LLM0. 로컬 HTTP로 테스트 판정 deferred→valid 저장 후 새 Dashboard에서 이력2건/최신valid 조회, 독립verification은failure 유지, JSON/CSV/MD/HTML 일치.
- 위 integration-test 검토는 개발용 가상 판정이며 실제 사람/독립2인검토 결과가 아니다. runs 원자료는 Git에 추가하지 않는다. 실제 사이트·유료API 검증은 이번 작업 범위가 아니다.

## 2026-10-11 C/P08

- 集중 지표·실험 검사15 passed (2.78s), 구현자 MVP/회귀 포함25 passed. scripted 분모7→5, 비유효 중앙값, null status, 저장 누락/legacy stale rate, bool 요청수의 거짓0을 실패 재현 후 수정했다.
- 무료 비교 `20261011T110414-9c0c68e4`: 일반/페르소나 각각 성공1/예정1, 요청6, 기록6/6·rate1. 비용은null/unknown1로 유지한다. 실제 LLM 성능 비교나 사람 행동 재현 증거가 아니다.
- doctor Python3.13.5/Playwright1.55.0/Chromium, study_errors없음. Mock 통합 `20261011T110505-f74829ea`: verified_success, 검색·필터·상세pass, 행동6/기록6.
- P08 작업 리뷰 지적1건 수정 후 해당 범위 blocker없음. 전체검사와 최종통합리뷰는 아래에 추가한다.

## C 최종 통합 검사

- 최종 코드 전체 pytest: **257 passed in 225.28s**. 수정 전236개 통과만으로 완료 처리하지 않고 새 실패 재현을 추가했다.
- Unicode JSONL과 실제 usage 누락 보완의 집중/통합 검사121 passed (211.83s), 안전 실행 ID 계약/저장51 passed. 통합 코드 리뷰의 두 지적과 추가 ID 호환 보완 후 Important/Critical blocker없음.
- 최종 CLI Mock `20261011T112434-c256adcb`: success, 검색·필터·상세pass, 6행동/기록6, 실제 측정토큰0/complete=true. 비용complete=false로 유지한다. 외부 유료 API 호출0.
- doctor / node --check / repo 검사 / diff 검사 통과. 1365×768 개선 보드에서 최신 판정·테스트 메모를 확인하고 가로 넘침없음. 기존 입력폼은 D 후속 범위다.
- 메모의 Unicode 구분자, 환경 비밀값 이스케이프, 동시저장/손상/경로, 비용·토큰·기록의 부분값, 실제 실행기→비교 저장→조회 경로를 검사했다.
- CI와 prototype 병합의 최종 상태는 관련 PR 기록에서 확인한다. 사람 독립 판정·실제 LLM 성능·실제 사이트 전체 평가는 이번 검사에 포함하지 않는다.

## 2026-10-13 D-01 (#32) 검토 입력·저장

- 기준: C PR #30의 b5bdffd 기반 `feat/32-candidate-review`. prototype 통합은 선행 PR 병합 후 별도 확인한다.
- 구현 전 실제 로컬 브라우저에서 `.review-form` 부재 실패를 재현했다. C 저장 API는 재사용한다.
- D-01 브라우저 12 passed (13.46s): 5종 판정 실제 HTTP 저장/새로고침, 과업 verification 유지, 메모 escaping, 400/404/409/500 입력 보존, 중복 제출 방지, 별칭·판정 필수, 실제 근거 버전 충돌 후 재조회, 모바일 가로 넘침 확인.
- 최종 기능 코드 전체 pytest: **269 passed in 91.55s**. 캡처 경로는 Windows 호환 `tmp_path`를 사용한다.
- doctor: Python 3.13.13 / Playwright 1.55.0 Chromium / study_errors 없음. JavaScript 구문·repo·diff 검사 통과.
- CLI mock 실행 `20261013T115852-e6bf1c84`: 독립 success, 검색/필터/상세 pass, 행동6·기록6/6. 외부 유료 API 호출 없음.
- 1365px 데스크톱 검토 폼 캡처를 확인했다. 390px 화면은 가로 넘침 없이 입력/저장 버튼을 제공한다.
- 위 판정은 개발용 합성 데이터·테스트 별칭이며 실제 사람 평가나 실사이트 UX 검증 결과가 아니다. 전체 이력 UI·전환/경합 회귀 확대·비교표·통합 시연은 #33~#36 후속이다.

## 2026-10-13 D-02 (#33) 초안·지연 응답

- D-01 PR #37의 59f67dc 기반. 자동 갱신·두 실행/카드 초안 보존·지연 저장 성공/실패는 기존 코드에서 통과했고, 지연 GET이 최신 판정을 미검토로 되돌리는 실패를 재현했다.
- 수정 후 전체 pytest **276 passed in 110.36s**. D-01 12개와 D-02 7개 브라우저 사례를 포함한다. 텍스트 포커스/선택, A→B→A 도중 옛 조회 무시, 실패 재시도와 다른 실행 저장 오염 방지를 검증했다.
- doctor Python 3.13.13/Playwright 1.55.0 Chromium 정상, JS 구문·repo·diff 검사 통과. CLI mock 검색/필터/상세 성공. 유료 API 호출 없음.
- 8765의 실제 화면에서 합성 상세 실패 실행 `20261013T121542-8e24cdfd`에 별칭·보류·미저장 메모를 넣고, 필터 실패 실행 `20261013T120550-f9b8ce5e`에 별도 초안을 작성한 뒤 왕복해 원래 값을 확인했다. 자동 갱신 후에도 유지됐다. 이번 수동 검사는 저장 버튼을 누르지 않았다.
- 새로고침/탭 종료 뒤 미저장 입력 복원은 지원하지 않는다. 카드 버전이 달라지면 이전 초안을 자동 적용하지 않는다. 실제 사용자 판단 데이터나 외부 사이트 검증이 아니다.

## D-03 사람 검토 이력·출처 (2026-10-14)

- D-02 PR #38 f196579 기반, #34. 관련 후속 #47은 Brain 기록 표시이며 이번 범위에 포함하지 않았다.
- 구현 전 새 이력 펼침 요소가 없어 브라우저 검사 1건 실패를 재현했다. 첫 샌드박스 실행은 로컬 소켓 권한 때문에 시작되지 않아 브라우저 실행 권한으로 다시 검사했다.
- 관련 브라우저 24개 통과(새 5개 포함), 전체 pytest 281개 통과(115.49초). 현재/이전 버전 분리, 두 번 저장·새로고침, 서버 시각, 메모 HTML 이스케이프, 390px 긴 버전 표시, 누락 출처 추정 금지, D-02 초안/지연 응답을 확인했다.
- repo 검사·diff 검사 통과. doctor: Python 3.13.13 / Chromium Playwright 1.55.0, study_errors=[]; 샌드박스 안에서는 Chromium 실행이 제한되어 허용된 환경에서 재실행했다.
- mock 통합 run 20261014T123055-19814b54: verification=success, verified_success, 6행동, 검색/필터/상세 pass. 실제 유료 모델·실제 사이트 검증이 아니다.
- 실제 로컬 대시보드에서 기존 합성 필터 결함 실행 20261013T120550-f9b8ce5e를 열었다. 사전 정의 스크립트/합성 테스트 환경 출처와 기존 검토를 확인하고 D03-화면검증 별칭의 테스트 보류 판정 1건을 추가했다. 기존 기록을 덮어쓰지 않고 2건이 표시되며 새로고침 뒤에도 별칭·판정·메모·시각이 유지됨을 확인했다. 이 기록은 실제 사용자 판단 데이터가 아니다.
- Mock 실행의 데모/미확인 출처도 실제 화면에서 확인했다. AI/live_configured 표시는 가상 API 표본으로 검증했다. 이전 버전 분리는 임시 실행의 근거를 변경하는 실제 HTTP/Chromium 테스트로 검증했다.
- 선행 #30 → #37 → #38과 prototype 통합 후의 검증 및 팀원 승인은 남아 있다. 이번 PR에서 병합하지 않는다.

## D-04 비교 측정 범위·누락 (2026-10-14)

- D-03 #49 aa3e115 기반 #35. 기존 C 집계를 재사용했으며 집계/저장 스키마 변경 없음.
- 구현 전 비교 범위 요소가 없는 실패 1건 재현. 신규 브라우저 5개 통과; 기존 D 검토 포함 29개 통과. 첫 전체 검사에서 없는 실행 버튼에 이동 ID가 남은 회귀 1건을 검출(285 통과/1 실패). 이동 ID 제거 후 관련 6개 및 최종 전체 **286개 통과 (123.01초)**.
- 실제 HTTP 집계→Chromium에서 2/5=40%, 성공0, 예정0, 취소/미실행, 부분값과 완전 측정/누락 포함 세션 수, 실제0/전체 누락, 기록0행동, 중앙값 계산 대상, scripted 제외, 없는 실행 비활성, 데이터 변경/자동 갱신 뒤 펼침 유지, 390px 가로 넘침 없음을 검사했다.
- 실제 로컬 화면은 기존 실행과 분리한 `/tmp/persona-d04-preview/runs`의 가상 표본을 8766 포트로 제공했다. 비용 전체 미확인·부분 $0.125, 토큰 부분120, 기록 전체 미확인·측정3/4=75%, 실제0원과 기록 대상행동 없음, 모델/환경 누락, 존재하는 실행 이동과 없는 실행 버튼 비활성을 확인했다. 가상 성능 수치이며 유료 모델/실제 사람/실제 사이트 결과가 아니다.
- doctor: Python 3.13.13 / Playwright 1.55.0 Chromium, study_errors=[]. Mock 20261014T124427-00482481: 6행동, verification=success, verified_success.
- repo/staged/diff 검사 통과. 선행 PR들의 prototype 통합 및 원격 CI/팀원 리뷰는 별도로 확인해야 한다. 회의록 정리는 이번 기능 문서와 별도 후속이다.

## codex 자동 CI와 D-03 D-04 원격 검사 (2026-10-14)

- push 대상에 codex/**를 추가했다. 수동 실행 없이 push 이벤트로 자동 시작됐으며 기존 권한과 검사 항목은 유지했다.
- D-03 #49의 2c42f67: [실행 38571360128](https://github.com/2026-2-1/Persona/actions/runs/38571360128). Ubuntu/Python3.11 281 passed (155.33초), Windows/Python3.13 281 passed (198.71초).
- D-04 #50의 f618818: [실행 38571422499](https://github.com/2026-2-1/Persona/actions/runs/38571422499). Ubuntu/Python3.11 286 passed (163.32초), Windows/Python3.13 286 passed (202.53초).
- 두 PR의 현재 head에 두 성공 check가 연결됨을 확인했다. 각 환경 repo 검사, doctor study_errors=[], Mock verification=success.
- D-04에 D-03 CI 변경을 병합하며 트러블슈팅 문서의 추가 문단 충돌을 해결했다. 양쪽 기록을 모두 보존했고 실행 코드 변경은 없다.
- prototype 병합과 팀원 승인은 별도다. 다른 브랜치도 이 워크플로 변경을 포함해야 codex push 검사가 실행된다.

## 2026-10-14 D-05 검토·내보내기 (작업 브랜치)

- 브랜치: `codex/36-review-export-verification`, 선행: D-04 #50 / 공유 문서 #51.
- 실제 합성 실행 `20261014T133938-52036475`: 후보 → 행동 6 화면/평가 근거 → valid 저장 → 새로고침 후 이력 1건 유지 → JSON/CSV/Markdown/HTML 대조 통과.
- HTML은 앱 내 브라우저 다운로드 도구 시간 초과 후 별도 Chromium의 실제 링크 다운로드로 확인했다. 나머지 세 형식은 앱 내 브라우저에서 다운로드했다.
- 신규 회귀 3개 포함 전체 pytest: **289 passed** (macOS, Python 3.13.13). 집중 검토·내보내기 검사: 30 passed.
- doctor: study_errors=[]; Mock: `20261014T135237-026b2a38`, verified_success, 6 actions. 실제 사용자/유료 모델 검증 아님.
- repo 검사 PASS. CI 결과는 해당 PR의 head 검사에서 확인한다.
- 근거 변경 시 Markdown/HTML에 현재 카드 버전이 없는 문제를 실패 테스트로 재현한 뒤 수정했다.
- 팀원 독립 재현, 전체 예외 상태 시연 및 prototype 통합 재검증은 남았다. [절차와 한계](tasks/d-review-export-verification.md).

## 2026-10-15 D 조회·출처·복구·예외 상태

- 선행 PR #52의 최종 CI [38575931790](https://github.com/2026-2-1/Persona/actions/runs/38575931790): Ubuntu 3.11/Windows 3.13 모두 success.
- `codex/d-dashboard-hardening`, #64/#65: 실패 테스트(조회/복구 4건, 출처 2건) 재현 후 수정. 집중 조회/검토 31 passed, 출처 3 passed, D-05/비교 12 passed.
- 전체 pytest **303 passed** (macOS Python 3.13.13). doctor 정상, repo 검사 PASS.
- 실제 Mock `20261014T165640-9f1f7163` verified_success. 새 run.json의 AI 실행/합성 출처 기록 확인.
- 실제 합성 실패 `20261014T165643-1173dceb`: 별도 임시 검토 이력 파일을 손상시켜 실제 API 오류 유발 → 마지막 정상 시각·초안 유지·저장 비활성 화면 확인 → 테스트 파일 복구 후 자동 재조회 회복 → 보존된 초안으로 deferred 저장 → 새로고침 후 이력 1건 확인. 개인/기존 실행 파일은 변경하지 않았다.
- 390px 정상/중단/빈 결과/근거 누락과 네 형식 내보내기 회귀를 추가했다. 독립 팀원 재현·prototype 통합은 남아 있다.

## 2026-10-15 Fast 단계별 생성 (#41)

- Fast의 perception·plan·decision을 별도 생성 요청으로 수행하고 단계별 입력 기억 ID, observation ID, plan ID, 생성 결과를 `brain_stages.jsonl`에 기록한다. perception·plan 생성 결과는 다음 단계 전에 메모리에 저장한다.
- Jev의 후보 선택과 생성 fallback, 완료 선언과 독립 평가 구분을 유지했다. Slow 작업 예약과 Brain 신규 조율은 포함하지 않았다.
- 전체 검사: **199 passed in 85.68s**. `python3 -m compileall -q src tests/test_fast_stages.py`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- Doctor: Python 3.14.5, Playwright 1.55.0 Chromium available, study_errors 없음.
- mock runner 통합은 독립 성공 판정, false-finish, 반복 상태 종료와 단계 기록·중간 메모리 저장을 확인했다. 실제 유료 LLM API는 호출하지 않았다.
## 2026-10-15 D Brain 기록 소비 (#47)

- 브랜치 `codex/47-brain-trace-viewer`, 선행 D 하드닝 PR #67.
- 기존 brain 필드/화면 패널 부재를 실패 재현하고 선택적 JSONL 읽기·6상태·제거 원본·내보내기를 연결했다.
- 전체 pytest **310 passed** (macOS Python 3.13.13), doctor 정상, repo/diff 검사 PASS.
- 첫 전체 검사에서 데스크톱 기본 화면의 세로 넘침 1건 발생: Brain과 비용의 접힌 패널을 같은 카드로 묶은 후 데스크톱 두 크기/390px/정확한 관찰 연결 및 전체 검사를 다시 통과했다.
- 소비 가상 표본: append 상태·원본 제거 이력·손상/교차 실행/심볼릭 링크·비밀값 제거·네 형식 대조. 생성 실행기와의 실제 Mock 통합은 별도 격리 체크아웃 검증으로 기록한다.
- D 하드닝 CI [38602694973](https://github.com/2026-2-1/Persona/actions/runs/38602694973): Ubuntu 3.11/Windows 3.13 모두 success.

## 2026-10-15 A+D 격리 통합 (#69)

- D 소비 d79a9b8 + A Fast 2c5f72a를 별도 checkout/preview에서 통합. 실행 출처와 Brain writer, C 실측 usage completeness를 함께 보존했다.
- 전체 pytest **324 passed** (macOS Python 3.13.13), doctor 정상, repo 검사 PASS. 테스트한 src/tests 트리와 최종 통합 merge 트리의 diff=0을 확인했다.
- 기존 C 사용량 기대값을 3 Fast+4 중요도 요청에 맞춰 보완하고 fast-stages-1 버전 기록을 실패 재현 후 구분했다.
- 실제 무료 Mock `20261014T171511-3d562d94`: 6 actions/42 interface requests/verified_success, 42 stage records/72 task events/24 latest tasks/24 original memories/warnings 0. 브라우저의 계획→정확한 관찰 연결 및 네 형식 다운로드 대조 통과.
- B live PR과 Slow 전체 조율, 팀원 재현·prototype 통합은 미포함. [아침 인수인계](handoffs/2026-10-15-morning.md).
추가 실제 시연에서 긴 Brain 목록의 출처 버튼이 이미지만 바꾸고 근거를 화면 밖에 남기는 문제를 발견했다. 30개 선행 기록을 넣어 viewport 검사 실패를 재현하고, 선택한 관찰 설명으로 이동하도록 수정했다. 출처/데스크톱 집중 4개를 통과했다.

원본 기억의 source_observation_ids/source_step_ids/source_stage_record_id도 표시한다. 단일 단계의 observation_id만 읽어 관찰 출처를 미기록으로 보이던 경우를 브라우저 실패로 재현하고 수정했다. 최종 소비 전체 310개 검사를 다시 통과했다.

최종 preview는 원본 기억 출처 보완 e20d7fb까지 포함해 전체 324개 검사를 다시 통과했다. 출처 화면 이동 보완 뒤 실제 브라우저의 선택 관찰도 viewport 안에서 확인했다. CI 결과는 각 PR의 현재 head 검사를 기준으로 읽는다.

### #41 PR 코드 리뷰 보완

형식이 틀린 첫 응답과 복구된 두 번째 응답을 fake provider로 재현했다. 수정 전에는 예산 요청 2회에 비해 Fast 호출 로그가 1건이었고, 수정 후 두 응답의 사용량을 각각 기록한다. `tests/test_fast_stages.py`: 3 passed, 전체 pytest: 200 passed (81.18s). 유료 API 호출 없음.

Jev가 입력 후보를 고른 뒤 생성 모델이 `give_up`을 반환하는 경로에서 null action 검사가 실패하는 것을 재현했다. 종료 선언을 보존하도록 수정했고 Fast·Jev 관련 검사 9개, 전체 pytest 201개(81.56s)가 통과했다. 유료 API 호출 없음.

## 2026-10-15 Slow 성찰·계획 검토 (#42)

- 전체 pytest: **204 passed in 80.86s**. Slow 전용 테스트는 대기열 무제한 예약, 비동기 호출, 성찰/계획 검토 기록, 고정 snapshot, provider 실패·timeout 기록과 mock runner 연결을 확인했다.
- `python3 -m compileall -q src tests/test_slow_loop.py tests/test_core.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- 신규 메모리 중요도는 5로 고정되며 점수 산정 API/작업은 실행되지 않는다. Slow 결과는 기존 계획을 바꾸지 않고 기록·메모리 후보만 추가한다.
- 네트워크 기반 유료 LLM 호출은 하지 않았다. 브라우저 통합 검사는 로컬 fixture와 mock provider를 사용했다.

### #42 PR 코드 리뷰 보완

Slow 모델이 잘못된 JSON을 반환해 작업이 실패해도 응답의 입력·출력 토큰을 별도 호출 로그에 기록한다. 수정 전에는 예산 요청 1회에 사용량 로그 0건이었다. fake provider 기반 Slow/Fast 관련 검사 4개, 선행 #41 수정 병합 후 전체 pytest 207개(81.38s) 통과. 유료 API 호출 없음.

## 2026-10-15 Brain 두 루프 조율 (#43)

- 전체 pytest: **212 passed in 82.28s**. fake provider 검사에서 stage 경계 reflection 채택, observation/plan ID/version이 맞는 plan review만 decision 문맥에 전달, stale 결과 폐기, 종료 시 실행 중·대기 작업 취소, general 조건 persona context 축소, run 메모리 격리를 확인했다.
- mock runner에서는 legacy `enable_slow_loop=false` 입력에도 Fast/Slow가 구성되고, Fast stage task ID와 stage record 연결, reflection/plan review 예약·상태 기록을 확인했다.
- `python3 -m compileall -q src tests/test_brain.py tests/test_brain_schema.py tests/test_slow_loop.py tests/test_fast_stages.py tests/test_model_selection.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- 요청 수/총토큰 제한은 기본 `null`이며 대기열 상한을 추가하지 않았다. 테스트는 가짜 provider와 로컬 fixture를 사용했고 실제 유료 API는 호출하지 않았다.

### #43 PR 코드 리뷰 보완

채택한 reflection을 일반 검색 결과에서 제외해도 다음 Fast decision 입력에 전달되도록 경계 결과를 우선 삽입한다. 기존 계획 검토의 정확한 observation/plan/version 검사와 입력 개수 상한은 유지한다. fake provider 및 mock runner로 재현했다. 선행 #41·#42 수정 병합 후 전체 pytest 216개(83.73s) 통과. 유료 API 호출 없음.

## 2026-10-15 Runner 평가 순서 (#44)

- 코드 변경: 초기 `evaluate()`의 조기 종료를 제거하고 행동 후 재관찰 또는 `finish` 선언 때 독립 평가한다. 단계 기록에 평가 근거와 관찰 시각을 연결한다.
- 검증 상태: 초기 성공·종료 선언·실행기 차단·후속 관찰 실패·모델 시간 초과·행동 중 중지의 mock runner 검사 6개와 전체 pytest 225개(91.75s)가 통과했다. 후속 관찰 뒤 summary가 이전 관찰을 가리키는 문제는 실패 재현 후 수정했다. 중지 시 현재 행동 기록과 비교 실행의 미시작 세션 보존, 페르소나 생성 중지에서 다른 실행을 건드리지 않는 동작은 전용 테스트로 확인했다. 실제 대시보드 하위 프로세스 검증에서는 `stopping` → `cancelled`, 취소 요약과 행동 시도·단계 기록 각 1건을 확인했다. `python3 -m uxagent run --study configs/study.json --provider mock --headless`는 처음에 로컬 포트 바인딩이 샌드박스에서 거부되어 실패했고, 허용된 권한으로 최종 재실행해 6회 행동 뒤 `verified_success`·기록 완전성 6/6을 확인했다. `node --check src/uxagent/dashboard/app.js`, Python compileall, 저장소 검사도 통과했다. 실제 유료 API/공개 사이트 성공은 확인하지 않았다.

## 2026-10-15 Persona 기반 Wonder (#45)

- 먼저 Wonder 전용 실패 재현 테스트를 작성했고, 초기에는 새 생성자 인자가 없어 5개가 실패했다. 구현 후 `python3 -m pytest -q tests/test_wonder.py` **13 passed**, 전체 `python3 -m pytest -q` **238 passed in 90.84s**.
- 고정 seed 139의 당첨·비당첨, 시작된 Slow 작업 ID별 1회 추첨, 일반 조건의 공통 제약만 전달, 제공자 내부 재시도, 요청 예산 부족, 활성 기억 N=10에서 과업 기억 보존과 기존 Wonder 우선 제거, 실행 종료 취소, 비밀 패턴 출력 거부, 대시보드·보고서 가정 표시를 확인했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture에서 행동 6회 후 `verified_success`, 기록 완전성 6/6, 시작된 Slow 작업 12개와 Wonder 추첨 12개. 무작위 seed 실행이라 이 실행에서는 당첨이 없었고, 고정 seed 139 당첨은 전용 mock runner 테스트로 확인했다.
- `git diff --check`, `node --check src/uxagent/dashboard/app.js`, `python3 -m compileall -q src tests/test_wonder.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py`: 통과. `python3 -m uxagent doctor --study configs/study.json`는 샌드박스의 Chromium 프로세스 등록 제한으로 첫 시도에 실패했고, 허용된 권한으로 재실행해 browser available·study_errors 없음으로 통과했다. 로컬 fixture와 mock/fake provider만 사용했고 유료 API·실제 사람 행동은 검증하지 않았다.

## 2026-10-15 두 루프 제공자·예산·비교 호환 (#46)

- 먼저 #46 전용 실패 재현 5개가 각각 예산 원인·Fast 재시도 로그·Slow 실제 provider·Jev 사전 차단·실행 모델 경로의 누락으로 실패했다. 구현 후 전용 검사는 14개가 통과했다.
- mock runner: `python3 -m uxagent run --study configs/study.json --provider mock --headless`에서 6회 행동 후 `verified_success`, 기록 완전성 6/6, LLM 호출 30회, Slow 작업 12개. 기본 요청/총토큰 상한은 `null`, 실행 상한은 30회 행동·300초로 유지했다. 이 결과는 이후 30회 행동의 비용/성공을 예측하지 않는다.
- 가짜 Jev/Gemini 제공자를 쓴 로컬 browser fixture에서 perception·plan·reflection·plan_review는 Gemini 모델, 후보 선택은 `jev-latest`로 기록되는 것을 확인했다. 키 누락·미지원 embedding은 실행 기록 또는 비교 세션 생성 전에 거부되는지 확인했다. 실제 유료 API 호출·계정별 모델 접근은 검증하지 않았다.
- 일반 조건에서 Fast·Slow·Wonder 생성 입력 전체에 persona 배경·숙련도·선호가 전달되지 않는지 확인했다. 의도치 않은 Slow persona 필드가 들어오면 비교를 차단하는 검사도 통과했다.
- `python3 -m pytest -q`: **252 passed in 96.24s**. `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. `python3 -m compileall -q src tests/test_provider_budget.py`, `python3 -m json.tool docs/tasks/manifest.json`, `python3 scripts/check_repo.py`, `git diff --check`: 통과.

## 2026-10-15 두 루프 기록 소비 (#47)

- 새 기록 소비 실패를 먼저 재현했다. 단계·작업·기억 로그를 만든 실행 상세에 `brain_tasks`와 `trace`가 없어 전용 테스트 2개가 실패했다. 구현 후 로컬 기록 소비·보고서 관련 24개가 통과했고, 새 Chromium 표시 테스트 1개와 데스크톱 높이 회귀 검사 2개가 통과했다.
- 첫 전체 검사에서는 새 최상위 기록 카드가 1365×768 화면 높이를 넘겨 **253 passed, 1 failed**였다. 기록 펼침을 기존 모델 호출 카드 안으로 옮겨 해당 브라우저 회귀를 수정했다. Wonder 부모 연결과 테스트 fixture 보완을 포함한 최종 `python3 -m pytest -q`는 **255 passed in 105.35s**였다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: `20261015T060054-5e8459e2`, 6회 행동·30회 모델 호출·12개 Slow 작업 뒤 `verified_success`, 기록 확보율 6/6. 해당 실제 로컬 기록의 상세 API에서 행동 trace 6건, 생성 단계 30건, 작업 사건 102건, 원본 기억 29건을 읽었고 JSON/CSV/Markdown/HTML 출력이 모두 열리는지 확인했다. 이는 로컬 fixture와 mock 모델의 동작 확인이며 실제 API/사이트 성과가 아니다.
- `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. `node --check src/uxagent/dashboard/app.js`, Python compileall, manifest JSON 파싱, `python3 scripts/check_repo.py`, `git diff --check`: 통과. 실제 유료 API·공개 사이트·인간 행동 유사성은 검증하지 않았다.

## 2026-10-15 공유 기억 중요도 산정 (#40)

- 원본 기억은 `null` 점수로 남기고 동일 ID·순번·생성 시각에 1~10점 변경을 적용하는 실패 재현 테스트를 작성했다. Slow의 비동기 점수 호출, 공통 예산, 제거된 기억의 늦은 응답 폐기, 잘못된 점수와 예산 소진 기록을 확인했다. 중요도 전용 5개 테스트가 통과했다.
- 첫 전체 pytest는 이전의 5회 모델 호출을 고정한 모델 선택 테스트 때문에 **257 passed, 1 failed**였다. fake provider와 호출 단계 기대값에 importance를 추가했다. 실패·예산 테스트 2개를 포함한 최종 전체 pytest는 **260 passed in 99.54s**, 중요도 전용 검사는 **5 passed**였다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture 실행 `20261015T061604-f58f1f64`에서 6회 행동 후 독립 판정 `verified_success`, 기록 확보율 6/6. 총 모델 요청 58회 중 중요도 요청 28회가 완료됐고, 원본 기억 29개는 모두 `null`로 남으며 28개 점수 변경 사건이 따로 기록됐다. 마지막 기억 1개는 종료 시 아직 산정 작업이 예약되지 않아 실행 요약 `importance_scoring_status=pending`이다. 이는 종료 시점의 미산정 상태를 숨기지 않는다.
- `python3 scripts/check_repo.py`, `python3 -m compileall -q src tests/test_memory_importance.py tests/test_model_selection.py`, manifest JSON 파싱, `git diff --check`: 통과. 위 검사는 mock/fake provider와 로컬 fixture만 사용했다. 실제 유료 모델의 점수 품질·추가 비용·공개 사이트 성공은 검증하지 않았다.

## 2026-10-15 메모리 검색 정책 (#54)

- 같은 입력에서 #40 동일 I/Q/R 기준선과 Fast 계획·행동 결정의 종류 가중치, Slow 최신성 가중 검색 순서를 비교했다. 미산정 기억과 점수 갱신, 60초 반감기, 알 수 없는 검색 mode를 전용 검사 5개로 확인했다.
- 첫 전체 pytest는 Slow 검색이 현재 관찰 원본을 밀어내 성찰 채택 테스트가 **263 passed, 1 failed**였다. 현재 관찰을 Slow snapshot의 필수 기억으로 추가한 뒤 관련 Brain·Slow·검색 검사 18개가 통과했다.
- 최종 전체 `python3 -m pytest -q`: **265 passed in 97.89s**. `python3 scripts/check_repo.py`, Python compileall, manifest JSON 파싱, `git diff --check`도 통과했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture `20261015T062424-1aa372d6`에서 6회 행동, 총 58회 mock 모델 요청, 독립 판정 `verified_success`, 기록 확보율 6/6, reflection 채택 5건을 확인했다. 실제 유료 API나 공개 사이트의 성공·시간 가중치 품질은 검증하지 않았다.

## 2026-10-15 활성 기억 제거 경계 (#55)

- 먼저 N=10 현재 단계 보호, N=12 미산정 대기 보존, N=10 대기 제거 이유, 임베딩 요청 중 제거 테스트를 작성했다. 4개 중 3개가 보호 API·우선순위·이유 누락으로 실패했다. 구현 후 오래된 Slow snapshot의 원본 출처 테스트도 포함해 전용 **5 passed**였다.
- 최종 `python3 -m pytest -q`: **270 passed in 97.54s**. 현재 단계·최근 10개가 충돌해도 활성 상한을 지키고, 제거 원본 ID와 Slow 출처, 제거 후 늦은 embedding 결과의 캐시 미복원을 확인했다. 최신 10개는 Wonder를 제외한 과업 기억에서 센다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture `20261015T063224-537d7a15`에서 6회 행동·58회 mock 모델 요청 후 독립 판정 `verified_success`, 기록 확보율 6/6. 기본 상한 64개에서 제거 경계는 발생하지 않았고 N=10/12 충돌은 전용 테스트로 확인했다. 실제 유료 API·공개 사이트·사람 행동은 검증하지 않았다.

## 2026-10-15 기억 점수·상한·출처 종합 검증 (#56)

- `tests/test_memory_integration.py`의 로컬 mock runner 2개(활성 상한 10·64)와 빈 기억·오래된 고점 제거/순번 테스트 1개를 추가했다. **3 passed in 6.84s**. 상한 10 실행에서는 제거 사건이 발생했고, 64 실행에서는 발생하지 않았다. 두 실행 모두 원본 기억 ID·점수 변경·Slow 작업/단계 출처·호출 수와 공통 예산을 대조했다. Fast 계획의 검색 기억 최대 6개와 별도 최근 행동 이력도 확인했다.
- 전체 `python3 -m pytest -q`: **273 passed in 102.92s**. 여기에는 #40의 점수 실패·예산·늦은 응답, #47의 이전 JSONL·null 행동, #54 검색 순위, #55의 N=10/12·Slow snapshot·embedding 경합, 기존 Slow 취소 회귀가 포함된다.
- mock/fake provider와 로컬 fixture만 사용했다. 실제 유료 API·공개 사이트 성공·사람 행동 유사성은 검증하지 않았다.
## 2026-10-15 실제 OpenAI 연결 / #57

- 증상: 실제 `gpt-4o-mini`로 합성 shop.html 과업을 실행하면 첫 결정에서 `model_error`로 종료됐다. 첫 실행은 `perception` 객체·`finish: false`, 프롬프트 1차 수정 후에는 `observation_id` 누락·`value` 필드 사용으로 `AgentDecision`/`Action` 검증에 실패했다.
- 원인: Fast Loop 시스템 프롬프트가 필드 이름만 나열하고 필드 형식과 행동별 허용 필드를 명시하지 않았다. mock·fake HTTP 테스트에서는 드러나지 않았다.
- 해결: 문자열 필드, action/finish 중 하나만 객체, finish 구조, 행동별 허용 필드를 프롬프트에 명시했다. 프로젝트 모델 목록의 OpenAI 단가(gpt-4o-mini 0.15/0.60, gpt-4.1-mini 0.40/1.60 USD per 1M, 표준 요금)를 추가했다. 공식 요금표 변경 시 갱신이 필요하다.
- 실제 실행(유료 API, 키는 로컬 `.env`): 수정 전 `20261014T153403-c958d7b5` model_error, 1차 수정 후 `20261014T154056-7b12da8f` model_error($0.00063), 최종 `20261014T154123-dda0d05a` verified_success 3행동·3요청·5,617토큰·$0.00102·10.8초, `20261014T154144-e76d8432` verified_success 2단계·2요청·3,556토큰·$0.00065·6.3초. 원자료 runs는 커밋하지 않는다.
- 전체 pytest 188 passed, 재현 테스트 3 passed, doctor 정상, mock verified_success, repository check PASS.
- 남은 범위: 데카트론 페이지의 AI 실행·판정 연결(P04), 실제 데카트론 검색 제출(#19), Claude/Gemini 경로의 같은 프롬프트 실측은 미검증이다. 반복 실행 수가 적어 형식 오류 재발률은 확인하지 않았다.

## 2026-10-16 prototype 병합 준비: #31/#58 호환

- 원격 보호 설정 승인 전 격리된 로컬 준비본에서만 작업했다. prototype 병합/브랜치 삭제 완료를 뜻하지 않는다.
- #31 협업 문서와 최신 #81의 연구/상태 링크를 모두 보존했다.
- #58의 행동 필드 명세를 최신 3단계 Fast의 decision 프롬프트에 연결했다. 기존 단일 decide 전제 테스트를 실제 decision API에 맞췄다.
- 날짜 snapshot 응답 모델의 비용 미확인과 프롬프트 필드 명세 누락을 2개 실패로 재현했다. 실제 응답 모델 식별을 유지하고 명시적으로 확인한 snapshot만 단가표에 추가했다. 알 수 없는 모델은 null을 유지한다.
- 단가는 [GPT-4o mini 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4o-mini)와 [GPT-4.1 mini 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4.1-mini)를 2026-10-16 확인했다. 입력/출력 토큰 기준 추정이며 계정 청구액·캐시 할인·기타 서비스 요금의 실측값이 아니다.
- 최종 준비본 전체 pytest 406 passed in 168.43s. 무료 Mock `20261015T164134-c9f17515` 종료 `verified_success`, doctor·Node·compileall·repo/staged·diff 검사 통과. 원격 prototype 병합은 보호 설정 변경 명시 허용 대기다.

## 2026-10-16 사용자 명시 허용 후 순차 병합

이번 작업에 한해 승인 수 1→0→1의 일시 변경을 허용받았다. CI·strict·관리자 적용은 유지하며 각 시도 직후 복원한다. 위 준비 당시 허용 대기 기록과 현재 권한을 구분한다. 원격 결과는 개별 PR의 squash commit과 최신 CI에서 확인하며, 전체 절차·로컬 검증·남은 문제는 [병합 기록](handoffs/2026-10-16-prototype-merge-queue.md)을 따른다.

#57 단계별 추가 호환: 팀원의 `fix/57-staged-openai-format`에서 인식·계획의 평문 문자열 요구를 보존했다. 해당 명세 누락 실패 1개를 재현한 뒤 수정했고 Fast/OpenAI/예산 관련 23개가 통과했다. 행동 결정의 기존 필드·미확인 모델 null 규칙은 유지한다. 실제 API 재검증은 수행하지 않았다.
## 2026-10-15 단계별 OpenAI 응답 형식 (#57, 팀원 staged 브랜치 기록)

- 단계별 Fast의 자료형·행동 필드와 `gpt-4o-mini` 가격 누락에 대한 테스트 2개가 수정 전 실패하고 수정 후 통과했다.
- `python3 -m pytest -q --tb=line`: **275 passed in 103.92s** (로컬 브라우저 서버 사용을 허용한 실행). 제한된 샌드박스 첫 시도는 소켓 생성 불가로 45 failed, 209 passed, 21 errors였으며 코드 회귀 판정에 사용하지 않았다.
- `python3 scripts/check_repo.py`: 0 problems. 실제 API 호출은 `OPENAI_API_KEY`가 현재 실행 환경과 로컬 `.env`에 없어 수행하지 못했다. 모델 형식의 실호출 성공은 미검증이다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless`: 로컬 fixture 실행 `20261015T064911-78e45798`에서 6회 행동·58회 mock 모델 요청 후 독립 판정 `verified_success`, 기록 확보율 6/6이었다. Python compileall과 `git diff --check`도 통과했다.

## 2026-10-15 합성 데카트론 AI 평가 연결 (#59)

- 평가 기대값을 설정에 넣은 실패 재현 3개가 기존 StudyConfig의 extra field 오류로 실패했다. 구현 후 가짜 단계별 제공자를 사용한 실제 로컬 브라우저 실행에서 일치 상세는 `verified_success`, 불일치 상세 2개는 `agent_finished`·`failure`였다. 정답 상품명은 모델 과업 문장에 넣지 않았다.
- 첫 전체 pytest는 기존 runner의 평가기 mock에 새 인자를 넘겨 **277 passed, 2 failed**였다. 기대값이 없는 기존 study의 호출을 유지하도록 수정한 뒤 관련 **10 passed**, 최종 전체 **279 passed in 108.03s**였다.
- `python3 scripts/check_repo.py`, Python compileall, study JSON 파싱, `git diff --check` 통과. 실제 OpenAI API 호출은 현재 로컬 키가 없어 수행하지 못했다. 제공자 실호출의 과업 성공은 미검증이다.

## 2026-10-15 공개 데카트론 AI 부분 평가 연결 (#61)

- 프로필 설정 수용·공개 설정 파일·상품명 키워드 판정의 실패 재현 3개가 수정 전 실패했다. 수정 후 데카트론 AI/평가기 관련 **28 passed in 16.12s**, 전체 **282 passed in 107.54s**였다.
- 로컬 Playwright DOM에서 다른 적합 러닝화 2개는 이름·8만원 이하 가격으로 성공하고, 신발 종류가 다르거나 가격이 99,900원이면 실패했다. 이 판정은 표시 상품명·가격의 부분 범위에 한정된다.
- `python3 scripts/check_repo.py`, Python compileall, live study JSON 파싱, `git diff --check` 통과. 실제 OpenAI API 키를 사용할 수 없어 공개 사이트 AI 실행은 수행하지 않았다. 이전 브랜치의 공개 사이트 기록을 현재 단계별 Fast 구현의 실호출 결과로 간주하지 않는다.

## 2026-10-16 원본 PR 순차 통합 최종 준비본

- A/B/C/D 통합 전체 pytest **416 passed in 174.46s**. 실제 브라우저의 검토·초안·새로고침·네 형식 출력, Brain 기록 및 합성 데카트론의 일치/불일치·profile 전달을 포함한다.
- 원본 #60의 다른 상품 종류 거부를 단계별 가짜 제공자에서도 보존했다. #58의 perception·plan 문자열 명세 누락을 실패 재현 후 팀원 staged 수정으로 보완했다. 제공자/호출 비용/예산 집중 23개, 데카트론 집중 29개 통과.
- 최종 무료 Mock `20261015T220538-00787cd2`: `verified_success`, 독립 success, 6행동·기록 6/6, 58 mock 요청. 계획 검토 채택 0건은 알려진 실행 순서 문제이며 해결 또는 연구 효과로 표시하지 않는다.
- Doctor Python 3.13.13 / Playwright 1.55.0 Chromium / study_errors 없음. Node 구문·repo/staged·diff 검사 통과. 유료 API·실제 공개 사이트·사람 평가 재검증은 수행하지 않았다.
- 원격 필수 Ubuntu/Windows CI를 각 최신 PR head에서 다시 확인한 뒤 squash 병합한다. 이 로컬 통과로 CI·승인 상태를 대체하지 않는다. [병합 절차와 남은 제한](handoffs/2026-10-16-prototype-merge-queue.md).

## 2026-10-16 Wonder seed 정밀도 보완 후 최종 검사

- 실제 생성된 7930736020609184225와 2**63-1에서 Chromium 표시가 바뀌는 실패 2개를 재현했다. 원본 정수·JSONL·출력 계약과 난수 정책을 유지하고 검증 draw 순서의 `wonder_seed_texts` 문자열로 표시한다.
- 화면·JSON/CSV/Markdown/HTML·원본 로그 불변을 실제 HTTP/Chromium으로 검증했다. 기존 Brain 소비·안전 읽기 포함 15 passed in 5.50s.
- 보완 후 최종 A/B/C/D 전체 **418 passed in 175.90s**. 앞선 416개 검증은 이 표시 보완 전 기록이며 합산하지 않는다. Node 문법·repo/staged·diff 검사 통과.
- 실제 유료 API·기업·사람 평가를 완료한 결과가 아니다. 계획 검토 실제 입력 도달·종료 집계 문제는 여전히 후속이다.

## 2026-10-16 #74 Windows 검사 안정화

동일 head의 Windows 결과가 달라 두 실패 사례를 분리했다. 기본 로컬 집중 2개, 성찰 12회 반복과 실제 Windows 집중 12회×2개가 통과했다. 6초 지연 조건에서는 성찰 0건·판정 행 0개 실패를 재현했고, 조회 준비 및 테스트 초기화 조건 보완 후 동일 루프 2개가 17.12초에 통과했다. 기능 검증 조건을 제거하지 않았으며 테스트의 실제 decision 도달을 추가 확인한다. 실제 PR의 Ubuntu/Windows 전체 CI를 다시 실행한다. 디버그 계측·축소 workflow는 병합 준비본에 넣지 않는다.

- 준비 조건 보완 후 #74 범위의 전체 **377 passed in 159.10s**, 최종 A/B/C/D 통합 범위의 전체 **418 passed in 176.77s**였다. 전체 검증 범위를 줄이지 않았다.
- 두 운영체제 원격 검사는 최신 PR head와 최종 prototype에서 별도로 확인한다. 진단용 부분 검사와 로컬 통과 기록은 원격 필수 CI 통과를 대신하지 않는다.

## 2026-10-16 로컬 GPU Qwen 연결

- 사용자 로컬 SSH 터널의 `/health`가 HTTP 200과 `{"status":"ok","model":"persona-qwen"}`을 반환했다. `/v1/chat/completions`는 기본 요청과 `response_format=json_object` 요청 모두 HTTP 200, `choices[0].message.content`와 `usage`를 반환했다.
- 새 `gpu` 제공자 코드의 실제 짧은 요청은 `{"ok":true}`와 입력 24·출력 8토큰을 반환했다. 대시보드의 연결 확인 경로도 실제 서버에서 `configured=true`, `validated=true`를 반환했다. 이 결과는 채팅 연결 확인이며 전체 과업 성공이나 모델 품질 검증이 아니다. 호출 비용은 미확인이다.
- 새 제공자·설정 도우미·대시보드·모델 선택 집중 검사는 **65 passed, 1 deselected**였다. 선택 모델의 전체 runner 검사는 합성 fixture가 로컬 8000번 포트를 필요로 해 제외했다. Node 구문과 Python compileall 통과.
- 전체 pytest는 GPU 터널이 합성 fixture와 같은 로컬 8000번 포트를 점유한 상태에서 **407 passed, 15 failed**였다. 실패한 mock 실행은 합성 페이지 제목 대신 빈 제목을 관찰했고, 같은 환경의 `/health`는 GPU API를 반환했다. 포트 분리 후 전체 재검사는 남아 있다.

## 2026-10-16 대시보드 평가 프로필 경로 수정

- 실제 실행 `dashboard-321082b0c6`의 두 세션 모두 `runs/.dashboard/decathlon_live_profile.json` 파일 없음으로 실패했고, 생성된 임시 study에 `evaluation_profile_file: decathlon_live_profile.json`이 남아 있음을 확인했다.
- 대시보드 실행용 study에는 원본 `configs/study-decathlon-live.json` 위치를 기준으로 해석한 절대 평가 프로필 경로를 저장한다.
- 전용 회귀는 수정 전 실패하고 수정 후 통과했다. GPU 제공자·대시보드 MVP·모델 선택 인접 검사는 **19 passed, 1 deselected**였다. 제외한 1개는 현재 GPU 터널과 같은 8000번 포트를 요구하는 전체 runner 검사다.

## 2026-10-16 개별 실행 실패 후 batch 계속 진행

- 실제 GPU 실행 `20261016T083126-9ee286d9`는 6단계에서 Qwen의 잘못된 `finish` 필드 때문에 `model_output_error`로 종료됐고 독립 판정은 `unknown`이었다. 이 실행 오류와 batch 전체 상태를 구분한다.
- 가짜 runner로 두 페르소나가 연속 실패하는 조건에서 두 호출이 모두 수행되고 실패 2건과 로그가 보존되며 batch가 완료 상태를 반환하는 회귀를 추가했다.
- 완료된 batch의 실패 모달에서 실패 수, 페르소나 ID, `model_output_error` 로그를 확인하고 닫는 브라우저 회귀를 추가했다. batch 계속 실행과 모달의 신규 회귀 2개는 수정 전 실패하고 수정 후 통과했다. 대시보드 완료 상태 회귀를 포함한 관련 검사는 최종 **18 passed in 4.15s**였다.

## 2026-10-17 Qwen 적용 PR 준비 검증

- `feat/90-qwen-application`에서 기존 수정 17개와 신규 `tests/test_gpu_provider.py`를 함께 검토했다. GPU 연결·모델 전달·평가 프로필 경로·개별 오류를 포함한 batch 완료·실패 모달 회귀를 포함한다.
- 로컬 8000번 포트가 비어 있는 환경에서 `python3 -m pytest -q`: **426 passed in 206.72s**. 앞선 포트 충돌 상태의 407 passed / 15 failed와 구분한다. Python 3.14.5 / pytest 8.4.2 / Playwright 1.55.0 Chromium에서 실행했으며, Python 3.11에는 pytest와 런타임 의존성이 없어 해당 버전 로컬 검사는 수행하지 않았다. Ubuntu 3.11 / Windows 3.13 검증은 원격 CI 결과를 별도로 확인한다.
- `python3 -m uxagent doctor --study configs/study.json`: Chromium available, study_errors 없음. 첫 샌드박스 실행은 Chromium의 macOS Mach port 권한 제한으로 실패했고 브라우저 실행을 허용한 환경에서 재검사해 통과했다.
- `python3 -m uxagent run --study configs/study.json --provider mock --headless --output runs/qwen-pr-mock-2026-10-17`: `verified_success`, 독립 `success`, 6행동·기록 6/6·58 mock 요청. GPU나 실제 공개 사이트의 성공을 뜻하지 않는다.
- `python3 scripts/check_repo.py`는 0 problems, Python compileall·Node 구문 검사·`git diff --check`도 통과했다. push 전 staged 경로·민감정보 검사와 파일 목록을 다시 확인한다.
- 이번 검증에서는 실제 GPU/유료 API/공개 데카트론을 새로 호출하지 않았다. 2026-10-16의 짧은 실제 GPU 연결 성공 및 전체 과업의 `model_output_error`·독립 `unknown` 기록을 그대로 유지한다. GPU 임베딩과 비용은 미확인이다.

## 2026-10-17 #83 U Fast 판단 전환

- 브랜치 `feat/83-u-transition-01`, 선행 Qwen 커밋 `264bd985ce3bd1744d4e692af52efdc719e61b00`, U 기준 `4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd`. 구현 범위와 U 대비 차이는 [#83 작업 문서](tasks/83-u-fast.md)를 따른다. 이 기록은 prototype 병합이나 #84~#90 완료를 뜻하지 않는다.
- 새 U 회귀 8개는 구현 전 실패, 구현 후 통과했다. 첫 전체 검사는 **426 passed / 8 failed in 198.43s**였다. 기존 응답 형식/Slow 예약 정책의 fake와 Mock 내부 재호출 집계 문제를 확인했다. 같은 잘못된 종료·반복·선택 모델·독립 평가 상황을 U 응답으로 옮기고 Mock 내부 변환을 실제 요청과 분리한 뒤 집중 **42 passed in 13.75s**였다.
- 최종 제품 코드의 전체 `python3 -m pytest -q --tb=short`: **439 passed in 203.56s**. 이후 추가한 가짜 GPU HTTP 두 차례 통합 1개도 통과했다. 해당 추가 사례를 포함한 `tests/test_u_fast.py` 전체는 **14 passed in 2.68s**이며 13개는 앞선 전체 검사와 겹친다. 이를 전체 440개 일괄 실행 결과로 표현하지 않는다.
- 신규 회귀는 Event 기반 후속 feedback/perceive 동시 시작·같은 HTML·첫 feedback 금지, old_plan/next_step 질의·계획 rationale/Thought 순서, 빈/복수 actions, 빈 observations, 잘못된 plan/JSON의 실제 토큰 기록·예산, 동시 호출 실패/취소의 형제 정리, 일반 조건 persona 비노출, 미지원 행동 원본 보존을 확인했다. 실제 Chromium type+Enter 제출과 도구 실패 이전의 제안 기억 파일 존재도 확인했다.
- 가짜 GPU HTTP 통합은 실제 `LocalQwenProvider`의 HTTP 요청/응답 처리와 runner·Chromium을 사용했다. 두 차례 클릭과 한 차례 feedback, persona-qwen 모델 유지·U 제안 및 도구 결과를 확인했다. 실제 GPU 서버 응답이나 공개 사이트 성공 검증은 아니다.
- doctor: Python **3.14.5**, Playwright **1.55.0** Chromium available, study_errors 없음. 무료 Mock 통합은 `verified_success`, 독립 success, **6행동·기록 6/6·28 mock 요청**, perception/plan/decision 각 6회와 feedback 5회 완료였다. 기존 성공 시 조기 종료 평가 정책은 #89까지 유지한다.
- `pip wheel --no-deps --no-build-isolation --no-index --no-cache-dir`로 패키징했다. wheel 안의 U 프롬프트 4개가 고정 원문과 byte 단위로 같고, 격리 Python의 wheel import에서 리소스를 읽는 것을 확인했다. repo 검사 0 problems, Python compileall·Node 구문·diff 공백 검사 통과. push 전 staged 검사와 파일 목록을 재확인한다.
- 실제 로컬 GPU `/health`는 URLError로 응답을 얻지 못했다. 실제 GPU 채팅·공개 데카트론 과업은 실행하지 않았다. Qwen 문맥/출력 한도, 큰 페이지 인식 완전성, 실제 과업 성능은 미검증이다. 선행 #91의 원격 Ubuntu/Python 3.11·Windows/Python 3.13 CI는 성공했지만 #83 head의 원격 결과를 대신하지 않는다.

## 2026-10-17 #84 U Slow·Wonder 반복

- 브랜치 `feat/84-u-transition-02`, 선행 Fast `4e42109a94898fb772a7c214221115ce25b75d66`와 Qwen #91을 포함한다. [작업 문서](tasks/84-u-slow.md)의 범위이며 prototype 병합·#85~#90 완료와 구분한다. 환경은 Python 3.14.5 / pytest 8.4.2 / Playwright 1.55.0 Chromium이다.
- 신규 7개는 구현 전 실패했고 신규 회귀 전체 **11 passed**였다. Event로 두 번 이상 순환·Fast 병행·최근50개·64개 이후 cursor·빈 입력/출력·ID 제거 뒤 늦은 응답·두 run 분리·취소/JSON/예산 실패를 검증했다. 새/옛 Slow **21 passed, 1 deselected**, 관련 Fast/Slow/모델/기억 **87 passed in 21.18s**였다.
- 첫 전체 `python3 -m pytest -q --tb=short`: **448 passed / 3 failed in 208.54s**. 종료 시 아직 응답하지 않은 Slow 요청의 usage도 측정됐다고 기대하던 테스트를 실제 시도/반환 횟수·미확인 전체값·측정 부분합을 확인하도록 수정했다. 제품의 usage 집계 정책은 바꾸지 않았다. 관련 **26 passed in 12.61s**였다.
- 두 번째 전체: **450 passed / 1 failed in 202.73s**. 반복 상태 판정 전에 `Page.screenshot`이 30초 시간 초과로 browser_error를 반환했다. 같은 사례 단독 **1 passed in 3.45s**였다. 브라우저 정책이나 제한을 수정하지 않았다.
- 마지막 전체: **448 passed / 3 failed in 217.96s**. 대시보드 클릭 30초, Chromium launch 180초 시간 초과와 모델 호출 전 브라우저 관찰 실패가 발생했다. 실패한 `test_check_status_rows_keep_distinct_states_and_open_evidence`, `test_demo_states_keep_verification_termination_and_missing_evidence[failure-scenario_failed-checks2]`, `test_runner_comparison_persists_actual_usage[missing]`를 이어 재실행해 **3 passed in 14.70s**였다. **전체 일괄 통과는 확보하지 못했으며** Chromium 전체 검사 안정성을 PR의 남은 검증으로 명시한다. 부분 재실행을 전체 통과로 합산하지 않는다.
- doctor: Chromium available, study_errors 없음. Mock CLI 합성 통합은 verified_success / 독립 success, **6행동·기록 6/6·1,302 mock 요청**이었다. Slow worker 1개·623회 순환, 종료 후 active/pending 0·cancelled·reserved_tokens 0·embedding_status=not_configured였다. 응답 전 취소 1건의 토큰은 미확인이며 brain 상태는 incomplete로 보존됐다. Mock의 빠른 응답/반복/요청 수는 GPU 속도·비용 지표가 아니다.
- 로컬 wheel 빌드에서 U Slow 프롬프트 3개가 고정 원문과 byte 단위로 같고 격리 import에서 읽힘을 확인했다. repo 검사 0 problems, Python compileall·git diff 공백 검사 통과. push 전 staged 검사·파일 목록을 확인한다. 별도 lint/typecheck 설정은 없다.
- 실제 GPU 채팅·embedding·공개 데카트론은 이번 작업에서 호출하지 않았다. GPU embedding은 미지원이며 설정 없이는 importance만 갱신한다. urllib의 이미 시작된 원격 HTTP 강제 취소·실제 과금 중단은 보장하지 않는다. #91/#92의 Ubuntu/Windows CI 통과는 이 브랜치의 새 head CI 결과를 대신하지 않는다.

## 2026-10-17 #85 U 기억 검색 선행 구현 (진행 중)

- `feat/85-u-transition-03`에서 [작업 문서](tasks/85-u-memory.md)의 순수 검색 수식·최근 목록·query embedding 계측을 구현했다. 실제 embedding 경로와 64개 초과 제거 순서는 이슈에서 요구한 사용자 결정 대기 상태다. PR/전체 구현 완료가 아니다.
- 점수/최근 경계/중복/top20/미준비/차원 8개 구현 전 실패 → 통과. query 호출·사용량/검증 오류 2개도 구현 전 실패 → 통과. 취소와 run 캐시 분리 포함 신규 전체 **11 passed in 0.16s**. 관련 순수 회귀 **36 passed in 0.25s**였다.
- Chromium 통합 첫 검사 **31 passed / 1 failed in 11.75s**. 임베딩 미설정인데 예전 단어 검색의 Action 4개 이상 입력을 기대한 사례였다. U 최근 목록만 반환하는 조건으로 기대값을 바꾸되 입력 Action 존재·원본/점수/제거·출처 검증은 유지했다. 해당 메모리 통합+신규 검색 **14 passed in 6.63s**였다.
- repo 검사0 problems·compileall·diff 공백 검사 통과. 전체 pytest·doctor·Mock CLI·실제 embedding·새 head CI는 아직 실행하지 않았다. 실제 GPU/데카트론 호출도 수행하지 않았다. 남은 결정을 반영한 뒤 실행한다.

- 후속 사용자 결정: 64개 초과는 중요도 낮은 순·동점 오래된 seq 순. 종류/단계 보호를 제거하는 신규2개가 변경 전 실패 후 통과했다. 검색·제거·점수·Slow 관련 **39 passed in 0.20s**. 미산정 null은 제거 순서에만0으로 취급하고 원본 null을 유지한다. 원격 GPU 임베딩 사용 의사는 확인했지만 실제 서버/모델/포트는 확인 중이며 SSH 비밀번호를 앱에 저장하지 않는 연결 안내를 development에 추가했다.

## 2026-10-17 #85 추가 결정·대시보드 GPU 수명주기

- 사용자 결정: 중요도 낮은 순·동점 오래된 seq 순. 이후 미산정0 우선 제거 시 채점된64개 뒤 새 기억이 성찰 전에 사라지는 실패를 재현했고, 사용자가 채점 전 임시 최상위 보존을 확정했다. 신규 회귀는 변경 전 실패 후 통과했다. 앞선0점 순서 기록은 이 최종 결정을 뜻하지 않는다.
- 사용자 제공 srun 옵션과 서버 실행법에 맞춰 sbatch/SSH master/분리 임베딩/준비 검사/소유 작업 반환을 추가했다. 기존 Qwen 환경은 수정하지 않는다. 상세 계약과 최초 준비는 [GPU 수명주기](tasks/gpu-dashboard-lifecycle.md)에 있다.
- 수명주기10개와 분리 embedding7개, U memory14개가 신규이며 모듈/메서드 부재·정책 차이 실패를 먼저 확인했다. 신규·기존 Slow/제거/중요도 집중 **52 passed in 0.92s**였다. 사용자 최종 결정 이전의 통합+신규 관련 검사는 **57 passed in 9.30s**였다. 첫 전체는 **477 passed / 3 failed in 207.10s**로 기존 종류/단계 보호·Wonder 우선 제거 기대와 새 중요도 정책이 달랐다. 해당 회귀의 입력/원본 기록 보존·점수·상한 검증은 유지하고 새 기대값으로 갱신했다.
- 임베딩 HTTP 검사는 실제 로컬 HTTPServer/urllib 전송을 쓰되 encoder와 벡터는 가짜다. 별도 embedding transport가 채팅의 embed를 호출하지 않고 같은 예산에 반영됨을 확인했다. 실제 CUDA/한국어 모델 품질 검증이 아니다.
- 원격 SSH 읽기 전용 점검은 BatchMode/StrictHostKeyChecking으로 수행했고 Permission denied(publickey,password)로 종료됐다. Slurm 명령/서버/GPU에는 접근·변경하지 않았다. 실제 Slurm 할당·서버 설치·모델 다운로드·GPU API/반환·공개 데카트론은 미검증이다. 로컬 비공개 설정과 첫 실행 안내를 runs/private에 준비했으며 저장소에 포함하지 않는다.
- 최종 정책 반영 전체 `python3 -m pytest -q --tb=short`: **482 passed in 224.32s**. 이 전체 실행 도중 반환 직전의 squeue 작업ID·고유 이름 동시 대조를 보강했고, 해당 보강 이후 신규/Slow/제거/중요도 집중 **52 passed in 0.81s**였다. 새 커밋 전체 원격 CI 결과는 PR에서 별도로 확인한다.
- doctor: Python3.14.5 / Playwright1.55.0 Chromium available, study_errors 없음. Mock CLI 합성 통합: verified_success / 독립 success, **6행동·기록6/6·1,262 mock 요청**, 단일 Slow worker·603회 순환·종료후active/pending0·cancelled. 임베딩 미설정/not_configured 조건이며 실제 GPU 임베딩이나 성능 지표가 아니다. 종료 취소 usage는 미확인으로 보존한다.
- wheel 빌드 후 gpu_session.py/embeddings.py/embedding_server.py가 현재 파일과 byte 단위로 같고 격리 import에서 원격 helper 리소스를 읽는 것을 확인했다. 예시 설정으로 생성한 원격 job script의 bash -n 통과. repo 검사0 problems·Python compileall·diff 공백 검사 통과. 별도 lint/typecheck 설정은 없다. staged 검사와 실제 파일 목록을 push 전에 확인한다.
