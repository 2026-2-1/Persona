# Claude 제공자와 안전한 모델 연결

관련 상위 이슈: #6

## 범위

공식 Anthropic Messages API 제공자를 추가한다. Claude·OpenAI·Gemini·Jev를 CLI/runner/연결/API 상태에 지원하고, 누락 키·잘못된 응답·실패 rollback·비노출을 검증한다. 실제 API/구독 PoC는 별도다.

## 완료 조건

- 구현과 실제 회귀 검사를 기록한다.
- 사용자 입력/선택 유지, 오류/미확인 상태를 보존한다.
- README와 관련 docs를 갱신한다.
- prototype 대상 PR로 리뷰·CI 후 머지한다.

## 구현 결과

Claude Sonnet 4.6, ANTHROPIC_API_KEY, Anthropic Messages API, 토큰 집계, 비용 미확인, HTTP/일시 오류와 키 rollback/비노출을 구현했다. fake HTTP/API 검증이며 실제 키 호출은 하지 않았다.
