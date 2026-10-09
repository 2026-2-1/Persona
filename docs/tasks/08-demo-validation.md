# 1차 최소 제품 통합 검증과 발표 시연

## 현재 상태 (2026-10-09)

MVP 통합 검증 완료 범위는 docs/verification.md에 기록한다. 실제 대상/API 시연과 발표 자료는 팀의 후속 점검이다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 01~07 완료

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

tests/; docs/verification.md, current-state.md; README.md

## 개발 순서

- [ ] 대표 과업 1개·persona 2종·환경 1개로 테스트와 비교 흐름을 검증한다.
- [ ] 예비 비용 확인 후 반복 수를 고정하고 정상·실패 결과를 저장한다.
- [ ] 카드·내보내기·근거·중지·오류 안내를 점검한다.

## 완료 조건

- [ ] Windows/Linux CI와 로컬 대표 흐름의 실제 결과를 기록한다.
- [ ] 기능 정상 동작과 과업 성공을 구분한다.
- [ ] 시연 화면에 실제 값/예시 값/미확인 표시가 정확하다.
- [ ] 10/16 발표에 구현·결과·한계·후속 계획을 설명할 수 있다.

## 실제 검증

doctor, 전체 pytest, repo 검사, mock 통합, 적격 실사용 시나리오를 별도 기록.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

작은 표본에서 persona 우위나 인간 행동 재현을 주장
