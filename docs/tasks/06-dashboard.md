# 초보자용 설정·테스트·비교 대시보드

## 현재 상태 (2026-10-09)

1차 화면은 디자인 기준으로 구현했다. 설정은 안내형 폼·계획 카드이며 자유로운 모델 대화 설정/근거 Q&A는 후속 기능이다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 03-metrics,04-ai-comparison,05-ai-connection

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/monitor.py, dashboard/index.html, dashboard/app.js; tests/test_dashboard.py

## 개발 순서

- [ ] 설정 대화와 확인 가능한 계획 카드를 연결한다.
- [ ] 과업 테스트와 AI 비교 메뉴를 각각 제공한다.
- [ ] 기능별 결과와 성공/전체 횟수, 오류·근거를 클릭해 조회한다.
- [ ] 진행/중지/연결 오류/빈 상태와 근거 기반 Q&A를 제공한다.

## 완료 조건

- [ ] 처음 사용하는 사람이 URL와 목표를 입력해 실행 계획을 확인할 수 있다.
- [ ] 미확인/미지원/측정 전을 0점이나 성공으로 표시하지 않는다.
- [ ] 최신 화면·선택한 과거 단계·현재 실행 따라가기가 유지된다.
- [ ] Q&A에는 근거 실행/단계 링크와 한계가 있다.

## 실제 검증

test_dashboard.py 경로/과거 run 혼입/최신 화면/실패 상태 회귀 및 브라우저 정상·실패·중지 시연.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

Next.js 전면 재작성, 임의 종합 UX 점수
