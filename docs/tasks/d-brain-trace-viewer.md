# D: Brain 기록 화면·보고서 소비 (#47)

최초 작업은 2026-10-15 `codex/47-brain-trace-viewer`와 D 안정화 PR #67 위에서 진행했다. 현재 `codex/latest-pr-integration-20261015`는 #79 + #78 후속 생성 실행기와 #75 소비 기능을 통합했다. [실제 통합 검증](../handoffs/2026-10-16-latest-pr-integration.md)을 따른다.

## 읽는 자료와 표시

- `brain_stages.jsonl`: perception/plan/decision/importance/reflection/plan_review/wonder 생성 결과와 기록 ID·관찰·계획 버전·기억 출처·snapshot.
- `brain_tasks.jsonl`: Fast와 Slow/Wonder 작업별 마지막 append 사건을 예약/진행/완료/채택/폐기/생략/실패/취소 8상태로 구분한다. 시각을 정렬해 이전 상태로 되돌리지 않는다. 전체 사건을 작업 펼침·API·내보내기에 보존한다.
- `memory.jsonl`: 원본 기억과 1.0(0–5)/2.0(1–10) 점수 척도. 미산정은 0으로 바꾸지 않는다.
- `memory_changes.jsonl`: 중요도 갱신과 활성 목록 제거를 overlay한다. 제거된 기억도 원본 텍스트·ID·순번을 읽을 수 있다. 원본 파일은 수정하지 않는다.
- `wonder_draws.jsonl`: 스키마를 검증한 실행 seed·부모 Slow 작업 ID·종류·추첨 순번/값·당첨 여부/작업 ID. 비당첨도 보존한다. 가정된 생각 1%를 실제 인간의 확률로 표시하지 않는다.

실행 기록의 접힌 ‘AI 생성·비동기 기록’ 하나에서 확인한다. #75의 별도 패널은 제거하고 선택 행동의 제안·도구 결과·재관찰·독립 판정 trace를 이 패널에 넣었다. 현재 상세에 관찰이 있으면 단계 생성에 사용한 정확한 관찰을 볼 수 있다. 단계·작업·기억의 펼침은 같은 실행의 자동 갱신에서 유지한다. AI 생성물·행동 제안은 실행된 행동이나 독립 평가·사람 검토·사람의 생각으로 표시하지 않는다. 완료/채택 사건만으로 후속 입력의 실제 소비를 추정하지 않는다.

파일 없음은 구버전 지원이며 생성 성공으로 보지 않는다. 잘못된 JSON·다른 실행 ID·지원하지 않는 버전·잘못된 단계/상태·심볼릭 링크는 경고와 함께 제외한다. 미완성 append 행도 조용히 성공 처리하지 않는다. 누락된 원본 기억 출처는 표시하며 다른 실행에서 대신 찾지 않는다.

## 출력 호환

`brain_trace.py`가 한 번 읽은 검증 자료를 JSON `brain`과 #75 최상위 별칭(`brain_stages`, `brain_tasks`, `memories`, `memory_changes`, `wonder.draws`), 행동 trace, 화면에 공통 제공한다. Markdown/HTML은 기존 카드/검토와 행동 trace·Wonder 설명·canonical Brain JSON을 보존하며 HTML 텍스트는 escape한다. 중복된 생성 기록 덤프는 만들지 않는다.

Brain 파일이 없는 기존 CSV는 카드 열 구성을 유지한다. Brain 파일이 있는 CSV는 기존 검토/카드 14열 뒤 `record_type,record_id,brain_record,stage_or_kind,status,text,observation_id,source_memory_ids`를 추가한다. 모든 행은 같은 열 수다.

- 카드 행: record_type=candidate.
- 추가 행: brain_stage/brain_task_event/memory/memory_change/wonder_draw/brain_warning/step.
- brain_record는 CSV 규칙으로 인코딩한 JSON이다. 분석 시 record_type으로 행을 구분해야 한다. 카드 ID가 없는 행을 후보로 세지 않는다.

원문 기록은 API와 모든 출력에서 기존 비밀값 제거를 적용한다. 모든 문자열은 텍스트 데이터로 처리하며 CSV 수식 실행과 HTML 삽입을 방지한다. 후보 버전은 Brain 기록 추가만으로 바뀌지 않고 독립 verification과 기존 집계 분모도 변경하지 않는다.

## 검증과 남은 범위

실패 재현: 기존 API의 brain 필드 부재, 기존 화면의 기록 패널 부재. 최신 통합에서는 Fast 작업과 adopted/discarded 누락, Wonder 추첨 미연결, 검증 reader와 raw 별칭 불일치를 3개 실패 테스트로 재현했다. 채택 배지 누락은 390px 브라우저 실패로 재현했다. 회귀는 8상태/마지막 append/제거 원본/점수 척도/손상·교차 실행·심볼릭 링크/비밀값 제거/단일 패널/행동 독립 결과/네 형식 출력 일치를 확인한다.

A의 실제 생성 코드와 통합한 Mock 검증은 통합 기록에 남긴다. Slow 조율과 stale 폐기는 이 브랜치에서 검증됐으며 실제 Mock의 plan_review 6건은 모두 폐기됐다. 사람 행동 유사성·유료 API·실제 사이트 성공·실제 입력 소비율은 미검증이다. #47 전체 종료는 팀원 독립 재현과 확정 prototype 통합 검증 뒤 판단한다.

긴 생성 기록을 읽다가 관찰 버튼을 누르면 해당 근거 화면의 설명 위치로 이동한다. 단순히 이미지 URL만 바꾸고 화면 밖에 남기지 않는 viewport 회귀도 확인한다.
