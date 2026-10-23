# #90 U 계약·로그·출력 최종 호환

## 구현 결과

U Fast/Slow/설문 API 호출을 현재 `llm_calls.jsonl`에 기록할 때 기존 provider/model/token/cost/error 필드를 보존하면서 schema v2 evidence를 추가했다. `call_id`, `method_name`, `recorded_at`, 요청 메시지, 원본 응답, 검색에 전달된 기억 목록을 한 행에서 복원할 수 있다. 실패 호출도 요청과 빈 응답을 기록한다. 입력·응답에서 인증정보 패턴이 탐지되면 근거 값 전체를 치환해 저장한다. 기록은 기존 `runs/<id>` 아래 로컬 append-only 파일만 사용한다.

원문 요청/응답/검색 결과는 대시보드 JSON API와 JSON/CSV/Markdown/HTML 내보내기에서 제외한다. 호출 메타데이터, 토큰/비용 누락, provider, 오류 정보는 기존 화면·집계 계약을 유지한다. 실행 상세는 `final_evaluation.json`을 읽어 추가로 제공하며 네 형식 내보내기에 최종 판정의 termination/observation provenance를 포함한다. 구형 실행에서 이 파일이 없으면 null로 읽고 파일을 고치지 않는다.

새 `feedback`/`thought` 기록, 설문 및 final evaluation이 UI 상세 reader/기존 내보내기에 연결되어 있다. 과거 plan_review/1% Wonder/adoption 이벤트는 계속 조회하지만 새 실행 의미를 과거 이벤트로 합성하지 않는다. source ID·시간은 trace 증거이며 결과 채택·모델 입력 우선순위·행동 허가 조건으로 사용하지 않는다. UI 레이아웃은 수정하지 않았다.

## 변경 순서

1. 호출 근거 helper에서 U stage→method 이름, 기록 시각/ID, request/response/retrieve_result 필드를 만들고 인증정보 검사를 적용한다.
2. Fast/Slow/사후 설문 호출 성공·실패 기록에 근거를 합친다. 기존 사용량과 오류 필드는 그대로 둔다.
3. 대시보드 상세의 호출 로그에서는 원문 근거를 제거하고 메타데이터만 제공한다. 결과 내보내기는 모델 요청 원문을 추가하지 않는다.
4. 상세 조회가 최종 독립 평가 JSON을 legacy-safe하게 읽게 하고 JSON 결과에 포함한다.
5. U feedback schema를 포함한 기존 reader/네 형식 출력과 구버전 기록을 회귀 검사한다.

## 저장 계약

새 호출 예시는 [공통 계약](../contracts.md#u-모델-호출-trace-v2-90)을 따른다. 기존 call 행은 schema_version 없는 형식도 허용하는 consumer가 읽으며 조회 중 원본을 재작성하지 않는다. 호출 전문은 로컬 `llm_calls.jsonl`에서만 확인할 수 있다. API/내보내기는 privacy boundary로서 호출 전문을 소비하지 않는다.

## UI 담당자 전달

D 통합 보완에서는 CLI `review.html`도 공통 호출 메타데이터 투영을 사용한다. 원본 request/response/retrieve_result는 로컬 JSONL에 유지하고 API와 HTML 검토 파일에는 포함하지 않는다.

- API `calls[]`에는 기존 module/stage/provider/model/usage/error/time 메타데이터만 제공한다. 로컬 전용 `request`, `response`, `retrieve_result`는 노출되지 않으므로 화면에 추가하려면 별도 민감정보 검토와 명시적 요구가 필요하다.
- run detail의 `final_evaluation`은 termination reason, final observation 식별자/URL/시각, 독립 evaluator 결과다. legacy run에서는 null이므로 “기록 없음”으로 읽어야 한다.
- 기존 UI 레이아웃은 변경하지 않았다. `termination_reason`과 `verification`은 서로 다른 축이며 모델 종료 선언을 성공으로 합치면 안 된다.

## 검증

- `tests/test_call_evidence.py`: U request/response/retrieve/method/time 연결, secret 포함 시 전체 근거 치환, API에서 호출 원문 제거, final evaluation provenance.
- `tests/test_u_fast.py`: 실제 fake-provider run의 새 U Fast 호출 행과 memory/search/response 연결.
- `tests/test_brain_trace.py`: 새 feedback stage와 legacy reflection/task/memory 기록의 네 형식 소비.
- 관련 상세/리포트/설문/runner 회귀와 전체 suite는 [검증 기록](../verification.md#2026-10-18-90-u-계약-로그-출력-통합)에 누적한다.

실제 GPU Qwen·공개 데카트론은 이 로그-reader 변경에서 호출하지 않는다. 실제 라이브 과업 결과로 간주하지 않는다.

고정 이슈: [#90](https://github.com/2026-2-1/Persona/issues/90). 원본 기준: [U LogApiCall](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/agent.py#L21-L50), [U memory 직렬화](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/memory.py#L225-L281), [U session trace](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/experiment.py#L135-L183).

2026-10-21 사용자 요청 후속: Qwen 공통 전송 전 입력 검사와 계층 요약을 연결했다. 추가 생성은 prompt_summary 단계와 parent_stage/round/chunk 메타데이터로 분리하며 기존 원문 비공개·usage·budget 계약을 유지한다. 실제 준비된 최종 메시지를 호출 근거로 남기고 원본 memory/관찰은 덮어쓰지 않는다. [공통 계약](../contracts.md)의 최신 요약 조건을 따른다.
