# D 후속: 조회 실패·출처·복구 측정 보완

2026-10-15. 관련 #64, #65, #36. 선행 PR #52 위의 `codex/d-dashboard-hardening` 작업이다.

## 조회 실패 (#64)

상세/비교 조회가 실패해도 정상 연결 및 후보/비교 없음으로 보이는 것을 실제 브라우저 검사로 재현했다. Promise.allSettled의 거절 결과를 무시하고 조회 상태를 별도로 관리하지 않은 것이 원인이었다.

상세·비교 조회 상태를 분리했다. 첫 조회 실패는 빈 결과가 아니며 재시도를 제공한다. 마지막 정상 상세가 있으면 조회 시각과 갱신 실패를 표시하고 작성 중 초안을 유지한다. 상세 조회 실패 중에는 판정 저장과 내보내기 링크를 비활성화하고 회복 후 복원한다. 비교 조회 실패만으로 정상 상세의 검토 저장을 막지는 않는다. 실행 선택 변경은 이전 상세를 즉시 지운다. 기존 run/card/version 초안 키와 지연 조회 revision 검사를 유지한다.

## 실행 출처·복구 (#65)

새 run.json에 execution_mode=ai를 기록한다. 내장 로컬 shop fixture는 synthetic_fixture, 나머지는 StudyConfig.source_kind의 명시적 값(unknown/synthetic_fixture/live_configured)을 기록한다. 실제 사이트 설정에는 source_kind=live_configured를 명시한다. 과거 기록은 소급 변경하거나 URL/provider로 출처를 추정하지 않는다. Mock은 화면에서 별도 Mock 데모로 표시한다. 합성 decathlon 지원 PR #60과 합칠 때 해당 is_fixture 판정도 보존해야 한다.

복구 rate=null은 미확인, 명시적 episodes=[]는 대상 사건 없음, rate=0은 0.0%로 표시한다. 복구 사건이 없다는 것은 전체 오류가 없거나 과업이 성공했다는 뜻이 아니다.

## 검증과 제한

`tests/test_dashboard_read_failures.py`는 상세 첫 실패/갱신 실패/초안 보존/저장·내보내기 차단/회복/비교 실패 독립성과 복구 상태를 검사한다. `tests/test_run_provenance.py`는 새 Mock 실행 기록·설정 검증·legacy unknown을 확인한다. D-05에는 정상/중단/빈 후보/근거 누락의 390px·네 형식 다운로드 대조를 추가했다.

팀원 독립 재현과 prototype 통합 재검증은 별도다. 이번 수정은 실제 사용자 행동이나 실제 LLM 성공 검증을 뜻하지 않는다.
