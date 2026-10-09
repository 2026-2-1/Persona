# 검색·필터·상세의 독립 평가기

## 현재 상태 (2026-10-09)

fixture 검색/필터/상세 최종 상태와 strict 외부 DOM/URL 확인 조건을 구현·검증했다. 빈 결과·필터 해제/초기화·실제 대상 4과업용 presets는 확장 범위다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 01-search-actions

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/evaluator.py, schemas.py; configs/; tests/fixtures/shop.html

## 개발 순서

- [ ] 대표 과업의 시작·입력·기대 결과·중단 조건을 실행 전에 정의한다.
- [ ] 검색 결과 갱신, 필터 가격 조건, 적용/해제 상태, 상세 필수 정보를 독립 판정한다.
- [ ] 코드 판정과 AI 보조/사람 판정을 구분한다.

## 완료 조건

- [ ] pass/fail/unknown/unsupported와 근거 observation을 기록한다.
- [ ] 모델 완료 주장으로 evaluator를 덮어쓰지 않는다.
- [ ] 성공·거짓 완료·빈 결과·필터 불일치·정보 누락을 검증한다.

## 실제 검증

tests/test_evaluator.py 신규: 정상/실패/미지원/잘못된 완료 사례. test_core.py mock 성공 회귀.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

범용 사이트 전체 정답, 모든 상품의 의미 관련성 확정
