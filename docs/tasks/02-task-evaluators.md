# 검색·필터·상세의 독립 평가기

## 현재 상태 (2026-10-11)

fixture 검색/필터/상세에 빈 결과·초기화·필수 상세 정보와 단계별 checkpoint를 추가했다. API 없는 합성 네 preset와 결함 재현, 근거 연결·개선 후보·내보내기가 구현됐다. 공개 데카트론은 지정 검색 결과 이름·가격 상한·상세 이름/가격만 부분 실행을 확인했다. 실제 대상 전체 네 과업과 색상·사이즈·재고·픽업은 후속이다. [사용법](../offline-scenarios.md), [실제 검증](../verification.md)을 따른다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 01-search-actions

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/evaluator.py, schemas.py; configs/; tests/fixtures/shop.html

## 개발 순서

- [x] 대표 과업의 시작·입력·기대 결과·중단 조건을 실행 전에 정의한다.
- [x] 합성 fixture의 검색 결과 갱신, 필터 가격 조건, 적용/해제 상태, 상세 필수 정보를 독립 판정한다.
- [x] 코드 판정과 AI 보조/사람 판정을 구분한다.

## 완료 조건

- [x] pass/fail/unknown/unsupported와 근거 observation을 기록한다.
- [x] 모델 완료 주장으로 evaluator를 덮어쓰지 않는다.
- [x] 성공·거짓 완료·빈 결과·필터 불일치·정보 누락의 fixture 검사 경로를 구현한다.

## 실제 검증

tests/test_decathlon_evaluator.py와 test_offline_scenarios.py에 정상·결함·미확인·중복/누락 근거·단계 연결 사례를 둔다. test_evaluator.py/test_core.py 기존 판정·mock 회귀를 유지한다. 실제 실행 결과는 verification.md에서 확인한다.

live `search_results`는 검색 URL·표시 이름이며 폼 제출이 아니다. `filters_price`는 URL 상한과 표시 카드 가격, `detail_basic`은 상품명·가격만 판정한다. partial/scope/unchecked_fields를 보존하고 전체 상품·색상·사이즈·재고·픽업 성공으로 확대하지 않는다.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

범용 사이트 전체 정답, 모든 상품의 의미 관련성 확정
