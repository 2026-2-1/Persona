# Brain 기록 도입 시 구버전 run 호환 계획

작성일: 2026-10-14. 상태: **구현 전 검토 문서**. [#39](https://github.com/2026-2-1/Persona/issues/39)의 기록 계약과 [#44](https://github.com/2026-2-1/Persona/issues/44)의 Runner 연결 사이에서 확인할 구버전 읽기 범위를 정한다. 이 문서는 마이그레이션 코드가 이미 존재한다는 뜻이 아니다.

## 목적과 원칙

기존 run의 `steps.jsonl`, `memory.jsonl`, `llm_calls.jsonl`, `summary.json`을 새 Brain 기록과 함께 대시보드·review·보고서에서 읽는다. 원본 run 파일을 다시 쓰지 않는다. 읽기 단계에서만 누락 필드를 해석하고, 실제로 기록되지 않은 observation·plan 버전·Slow 작업·평가 근거를 추측해 생성하지 않는다. 구버전 Fast의 단일 `AgentDecision`을 새 perception/plan/decision 세 번의 실제 LLM 호출로 표시하지 않는다.

## 확인된 현재 형식

| 기록 | 구버전에서 가능한 모습 | 새 계약과 읽기 규칙 |
|---|---|---|
| `memory.jsonl` | `schema_version`, `source_memory_ids`, `source_stage_record_id` 없음. 중요도는 0~5 또는 null | `MemoryEntry`는 누락 버전을 1.0, 출처 목록을 빈 목록으로 읽는다. 빈 목록은 출처가 **기록되지 않았음**을 뜻하며 출처가 없었다는 증거가 아니다. 새 2.0 항목의 중요도는 논문 기준 1~10 또는 null이다. 두 척도를 같은 숫자로 취급하지 않는다. |
| `steps.jsonl` | 결정 안에 perception·plan·action/finish가 함께 있음. 모델 오류나 종료 선언은 `action`·`result`가 null일 수 있음 | 기존 결정을 그대로 유지하고, 새 `BrainStageRecord`가 없으면 단계별 기록은 미기록으로 표시한다. `finish.claim=completed`를 evaluator의 `verification=success`로 바꾸지 않는다. |
| `llm_calls.jsonl` | 요청·토큰·비용 필드가 일부 없거나 null일 수 있음 | 확인되지 않은 수치의 화면 표시와 집계는 `unknown`/`null`을 유지한다. 실제 0이 확인된 mock/scenario 호출만 0으로 취급한다. |
| `summary.json` | Brain 단계·비동기 작업 기록이 없고 기존 `verification`, `termination_reason` 중심 | 독립 평가와 종료 사유를 그대로 읽는다. 새 Brain 작업의 미기록을 `completed`나 `failed`로 추정하지 않는다. |

`BrainStageRecord`, `BrainTaskEvent`, `MemoryChangeEvent`는 #39에서 형식만 정의했다. 현재 Runner는 이 사건을 쓰지 않는다. #44에서 새 실행 기록을 연결하더라도 과거 실행에 사건을 소급 생성하지 않는다.

## 구현 위치와 순서

1. `schemas.py`의 구버전 `MemoryEntry` 파싱을 기준으로 실제 구버전 JSONL 표본을 읽는다. 버전이 없으면 기존 형식으로 취급하고, 명시된 미지원 버전이나 잘못된 필드 값은 조용히 현재 형식으로 바꾸지 않는다.
2. `monitor.py`의 `Dashboard.state()`·`run_detail()`, `review.py`의 review/인터뷰, `reports.py`의 카드·내보내기, `metrics.py`의 집계가 누락 필드와 null 행동/결과를 어떻게 사용하는지 확인한다. 필요한 읽기 호환 처리는 소비 경로에서 최소 범위로 적용한다.
3. 원본이 보증하는 연결만 보존한다. 구버전 `step_id`, `observation_id`, `memory_id`, 평가 결과는 유지한다. 과거에 기록되지 않은 `plan_id`, plan 버전, snapshot 순번, 메모리 출처, 실제 사람 선호는 `null`/미기록으로 남긴다.
4. `monitor.py`의 진행 중 run 토큰 합계처럼 누락 토큰을 `0`으로 대체하는 표시 경로를 확인한다. 일부 호출의 토큰 또는 비용을 모르면 전체 합계도 미확인으로 표시하고, 확인된 개별 호출 값은 보존한다. 이 변경은 비용 산정 방식 자체를 바꾸지 않는다.
5. 새 파일이나 필드를 읽는 화면·보고서를 추가할 때는 **기록 없음**, **실패**, **미확인**을 구분한다. 과거 run에 Brain 사건이 없다는 이유로 과업 결과나 사람 검토 상태를 바꾸지 않는다.

## 회귀 검증과 완료 기준

- 버전 필드가 없는 구버전 `memory.jsonl`의 0~5점과 새 2.0 항목의 1~10점을 각각 파싱·직렬화한다. `importance=None`도 점수 미산정으로 보존한다.
- 구버전 `steps.jsonl`의 정상 행동, `action=null`/`result=null` 종료, 행동 뒤 관찰 실패를 각각 대시보드 상세·review HTML·보고서 JSON/CSV/Markdown/HTML로 읽는다. 예외가 나거나 행동을 실행한 것으로 꾸미면 실패다.
- 제거된 활성 메모리의 원본 JSONL과 그 ID를 참조하는 새 기록을 함께 읽는다. 원본 출처를 지우거나 새 ID를 부여하면 실패다.
- 토큰·비용이 빠진 호출과 실제 값 0인 호출을 분리해 표시·집계한다. 전자는 미확인, 후자는 0이어야 한다.
- 기존 `tests/test_metrics.py`, 대시보드·review·보고서 회귀와 새 구버전 run 통합 표본을 실행한다. 실제 검사 결과만 `docs/verification.md`에 적는다.

완료 기준은 **과거와 새 run 모두 원본을 보존한 채 소비 경로에서 열리고, 없는 근거가 생성되지 않으며, 알려지지 않은 비용·판정이 성공 또는 0으로 바뀌지 않는 것**이다. 실제 Brain 단계의 생성·기록은 #44에서 별도로 검증한다.
