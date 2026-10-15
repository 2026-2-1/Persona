# 검증 기록

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

## 2026-10-15 D Brain 기록 소비 (#47)

- 브랜치 `codex/47-brain-trace-viewer`, 선행 D 하드닝 PR #67.
- 기존 brain 필드/화면 패널 부재를 실패 재현하고 선택적 JSONL 읽기·6상태·제거 원본·내보내기를 연결했다.
- 전체 pytest **310 passed** (macOS Python 3.13.13), doctor 정상, repo/diff 검사 PASS.
- 첫 전체 검사에서 데스크톱 기본 화면의 세로 넘침 1건 발생: Brain과 비용의 접힌 패널을 같은 카드로 묶은 후 데스크톱 두 크기/390px/정확한 관찰 연결 및 전체 검사를 다시 통과했다.
- 소비 가상 표본: append 상태·원본 제거 이력·손상/교차 실행/심볼릭 링크·비밀값 제거·네 형식 대조. 생성 실행기와의 실제 Mock 통합은 별도 격리 체크아웃 검증으로 기록한다.
- D 하드닝 CI [38602694973](https://github.com/2026-2-1/Persona/actions/runs/38602694973): Ubuntu 3.11/Windows 3.13 모두 success.

추가 실제 시연에서 긴 Brain 목록의 출처 버튼이 이미지만 바꾸고 근거를 화면 밖에 남기는 문제를 발견했다. 30개 선행 기록을 넣어 viewport 검사 실패를 재현하고, 선택한 관찰 설명으로 이동하도록 수정했다. 출처/데스크톱 집중 4개를 통과했다.

원본 기억의 source_observation_ids/source_step_ids/source_stage_record_id도 표시한다. 단일 단계의 observation_id만 읽어 관찰 출처를 미기록으로 보이던 경우를 브라우저 실패로 재현하고 수정했다. 최종 소비 전체 310개 검사를 다시 통과했다.
## 2026-10-15 Fast 단계별 생성 (#41)

- Fast의 perception·plan·decision을 별도 생성 요청으로 수행하고 단계별 입력 기억 ID, observation ID, plan ID, 생성 결과를 `brain_stages.jsonl`에 기록한다. perception·plan 생성 결과는 다음 단계 전에 메모리에 저장한다.
- Jev의 후보 선택과 생성 fallback, 완료 선언과 독립 평가 구분을 유지했다. Slow 작업 예약과 Brain 신규 조율은 포함하지 않았다.
- 전체 검사: **199 passed in 85.68s**. `python3 -m compileall -q src tests/test_fast_stages.py`, `python3 scripts/check_repo.py` (0 problems), `git diff --check` 통과.
- Doctor: Python 3.14.5, Playwright 1.55.0 Chromium available, study_errors 없음.
- mock runner 통합은 독립 성공 판정, false-finish, 반복 상태 종료와 단계 기록·중간 메모리 저장을 확인했다. 실제 유료 LLM API는 호출하지 않았다.

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
