# 쉬운 API 연결과 ChatGPT 구독 연동 PoC

## 현재 상태 (2026-10-09)

API 키의 서버 세션 보관·실제 소규모 연결 확인·실패 rollback은 구현했다. 실제 키 호출과 ChatGPT 구독 OAuth는 미검증/미구현이며 별도 PoC가 필요하다.

아래 체크리스트는 전체 목표이며 현재 상태 문단과 구분한다. 구현·검증된 항목은 후속 작업에서 중복 구현하지 않는다.

## 목적과 선행

선행: 기본 키 경로는 독립; 구독 경로는 적격성 확인 선행

읽을 문서: docs/current-state.md, roadmap.md, contracts.md, troubleshooting.md 및 AGENTS.md.

## 변경 영역

src/uxagent/llm.py, monitor.py, dashboard/; 별도 Responses provider; tests/test_connection.py

## 개발 순서

- [ ] 데모/API 키/지원 확인된 ChatGPT 연결 경로를 구분한다.
- [ ] 키는 서버 세션에서 관리하고 프런트엔드·로그·저장소에 넣지 않는다.
- [ ] 구독 PoC는 공식 OAuth 권한과 적격 Responses 계약, 모델 가용성을 확인한다.
- [ ] 로컬/공개 호스팅 조건을 구분하고 확인 전 구독 사용을 약속하지 않는다.

## 완료 조건

- [ ] 연결 성공·키 누락·잘못된 키·권한 거절·한도 도달을 설명한다.
- [ ] 키/토큰이 상태·로그·내보내기에 포함되지 않는다.
- [ ] 구독 실패 시 API로 자동 결제 전환하지 않는다.
- [ ] PoC 결과/제한/사용량 관리 링크를 문서화한다.

## 실제 검증

네트워크 fake로 인증·실패·키 비노출 검사. 실제 구독 PoC는 적격 계정과 동의가 있을 때 별도 결과 기록.

검사 결과는 완료 시 이슈와 docs/verification.md에 기록한다.

## 범위 밖

공개 서비스 구독 지원 보장, 비공식 인증 우회
