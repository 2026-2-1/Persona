# 일반 AI·페르소나 AI 대응 비교 실행

## 현재 상태 (2026-10-09)

1차 MVP 구현 완료. 일반 프롬프트·artifact 분리, 구매 제약 유지, 사전 등록·shuffle seed·고정 분모·중지 상태·근거 연결을 검증했다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 03-metrics

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/schemas.py, fast_loop.py, runner.py, cli.py; 새 experiments.py; tests/test_experiments.py

## 개발 순서

- [ ] 일반 조건에서 인물 배경·탐색 성향만 제외하고 같은 구매 제약은 유지한다.
- [ ] 동일 과업·모델·환경·호출 상한의 대응 세션을 구성하고 실행 순서를 seed로 섞는다.
- [ ] 새 브라우저 context로 분리하고 성공 후 불필요한 호출을 추가하지 않는다.

## 완료 조건

- [ ] 일반 조건 프롬프트에 persona 배경이 들어가지 않는다.
- [ ] 대응 블록과 실제 조건·호출·비용을 추적할 수 있다.
- [ ] 취소·실패도 비교 데이터에 남는다.
- [ ] 소수 반복은 예비 결과라고 표시한다.

## 실제 검증

입력 프롬프트 캡처로 두 조건 차이 검증; seed 재현·context 격리·예산/취소 검사.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

Jev 변경과 persona 효과의 동시 비교
