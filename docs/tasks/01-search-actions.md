# 검색 입력과 세부 행동 지원

## 현재 상태 (2026-10-11)

실제 입력값 생성/교체와 옵션 ID 충돌 회귀에 더해 한정된 keypress, 명시적 scroll, 관찰된 custom control 클릭/키 후보를 구현했다. API 없는 사전 정의 시나리오에서 정상 검색·검색어 교체·빈 결과·화면 밖 안내를 수행한다. Jev 후보에 완료/진행 불가 종료를 추가했으며 성공은 독립 평가로 확인한다. 범용 custom control 지원은 후속이다. [사용법](../offline-scenarios.md)과 [실제 검증](../verification.md)을 따른다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 없음

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/fast_loop.py, schemas.py, observation.py, actions.py; tests/test_regressions.py

## 개발 순서

- [x] 과제 문장과 실제 입력값을 분리하고 검색어를 생성한다.
- [x] Enter 제출과 필요한 scroll 지원을 별도 schema/관찰 계약으로 정의한다.
- [x] Jev 후보에 완료/진행 불가 종료 경로를 정의하되 fallback과 예산을 유지한다. 별도 판단 보류 분류는 추가하지 않는다.

## 완료 조건

- [x] 정상 검색어·검색어 변경·빈 결과 경로를 fixture에서 수행한다.
- [x] stale ID·허용 origin·password 금지와 기존 mock을 보호하는 검사 경로를 유지한다.
- [x] 새 행동 미지원 시 이유를 표시하고 완료로 처리하지 않는다.

## 실제 검증

tests/test_extended_actions.py, test_offline_scenarios.py와 기존 test_regressions.py/test_core.py에서 새 키·scroll·관찰 후보·범위 차단과 mock 회귀를 검사한다. 전체 pytest·mock·대시보드의 실제 결과는 verification.md에 기록한다. checklist는 구현 범위이며 미실행 검사가 통과했다는 뜻이 아니다.

공개 사이트 지정 검색 결과의 가격/상세 부분 실행은 확인했다. 홈페이지 한글 입력/폼 제출은 별도 시도에서 unknown이며 순차 입력 옵션을 추가했다는 사실만으로 해결 완료라고 쓰지 않는다.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

전체 UI 교체, 결제/로그인, 외부 사이트 성공 단정
