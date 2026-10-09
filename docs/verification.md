# 검증 기록

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
