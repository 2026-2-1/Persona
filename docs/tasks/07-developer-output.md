# 개발자 개선 카드와 HTML·Markdown·CSV/JSON 출력

## 현재 상태 (2026-10-09)

미검토 개선 카드와 HTML/Markdown/CSV/JSON 출력·XSS/키 제거 검사를 구현했다. 사람 판정 저장·합의·발생 범위·개선 전후 재검증은 확장 범위다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 03-metrics,06-dashboard

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/review.py, monitor.py, dashboard/; 새 reports.py; tests/test_reports.py

## 개발 순서

- [ ] docs/contracts.md의 카드 필드와 검토 상태를 구현한다.
- [ ] 관찰 사실·원인 가설·개선 제안·완료 조건·회귀 검사를 분리한다.
- [ ] 사이트 UX 후보와 도구/환경 오류를 별도 목록으로 제공한다.
- [ ] 동일 카드 데이터로 UI와 각 내보내기를 생성한다.

## 완료 조건

- [ ] 근거가 없으면 미확인 표시하고 소스 파일/라인을 만들어내지 않는다.
- [ ] 미검토 후보·확정·보류·중복을 내보내기에도 보존한다.
- [ ] null action/result와 악성 HTML 문구에도 보고서가 정상 생성된다.
- [ ] 출력에서 키·인증정보·민감 원자료를 제거/검토한다.

## 실제 검증

tests/test_reports.py: null/근거 누락/HTML escaping/CSV·JSON 동일 ID/키 비노출. review 기존 회귀.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

외부 GitHub 이슈 자동 등록, 미검증 원인 확정
