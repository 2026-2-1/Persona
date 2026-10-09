# 검색 입력과 세부 행동 지원

## 현재 상태 (2026-10-09)

실제 입력값 생성/교체와 옵션 ID 충돌 회귀는 구현·검증했다. Enter/scroll/custom control 및 종료 후보는 후속 개발이다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 없음

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/fast_loop.py, schemas.py, observation.py, actions.py; tests/test_regressions.py

## 개발 순서

- [ ] 과제 문장과 실제 입력값을 분리하고 검색어를 생성한다.
- [ ] Enter 제출과 필요한 scroll 지원을 별도 schema/관찰 계약으로 정의한다.
- [ ] Jev 후보에 종료/판단 보류 경로를 정의하되 fallback과 예산을 유지한다.

## 완료 조건

- [ ] 정상 검색어·검색어 변경·빈 결과 경로를 fixture에서 수행한다.
- [ ] stale ID·허용 origin·password 금지와 기존 mock이 유지된다.
- [ ] 새 행동 미지원 시 이유를 표시하고 완료로 처리하지 않는다.

## 실제 검증

tests/test_regressions.py와 test_core.py에 검색 입력/제출/종료 후보/범위 차단 사례를 추가. 전체 pytest와 mock 실행.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

전체 UI 교체, 결제/로그인, 외부 사이트 성공 단정
