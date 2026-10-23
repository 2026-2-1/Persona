# #88 U 질문지·전체 기억 trace 기반 사후 설문

## 목표

고정 세 문항과 실행 성공 문구 조합을 제거하고, 질문지와 run의 전체 append-only 기억 trace를 선택 모델에 전달해 실제 모델 응답을 생성한다. GPU 실행에서는 Qwen `persona-qwen`을 사용한다. 이 결과는 `simulated_self_report`이며 사람 응답이나 evaluator 판정이 아니다.

## 변경 전 → 변경 후

| 변경 전 | 변경 후 |
|---|---|
| `create_survey`가 고정 질문 3개에 성공 여부·반복 오류를 문장으로 합성 | 설정 가능한 질문지 + 실제 기억 trace를 LLM에 전달하고 모델 답을 검증 |
| 모델 호출·usage·provider 오류 없음 | `llm_calls.jsonl`, run 요약, batch 집계에 설문 요청·토큰·알 수 없는 비용 반영 |
| 누적 기억이나 제거된 기억을 소비하지 않음 | 전체 `memory.jsonl`을 순서대로 포함하고 importance 이벤트의 최신 점수를 복원 |
| 세션 종료 여부와 무관하게 독립 함수 호출 | batch의 모든 브라우저 세션이 끝난 뒤 각 run의 사후 설문 실행 |

## 기억 범위 결정

2026-10-20 사용자 후속 변경: 전체 trace는 그대로 유지하며 각 기억의 content_status를 포함한다. 세 번째 JSON 줄로 steps.jsonl의 실제 행동·성공/실패·오류·전후 URL과 종료 사유를 제공한다. 계획/생성 생각을 실행 증거로 취급하지 않는다. evaluator 결과·기대값은 보내지 않는다. 실행 기록이 있을 때 응답 meta.execution_error_count가 실제 실패 수와 일치해야 하며, 누락/불일치는 execution_fact_mismatch다. subjective 답변은 여전히 unverified_simulated_self_report이며 오류 수 검증을 답변 전체의 사실 확인으로 해석하지 않는다.

이후 실패한 설문 재실행은 이전 survey.json을 survey.previous-<id>.json으로 보존하고 현재 답변에서 제외한다. 원본 응답·새 실패 상태는 survey_result에 남긴다. 실제 20261020T121820-e98c2e82 기록의 임시 사본으로 재생한 Qwen은 오류3건과 검색 미제출을 구분했다. 검증 기록을 따른다.

Owner는 **전체 누적 trace**를 선택했다. 설문은 `memory.jsonl`의 모든 기억을 `seq` 오름차순으로 사용한다. `memory_changes.jsonl`에서 최신 `importance_scored.importance_after`를 복원하고 `evicted` 기억도 포함한다. 검색용 활성 기억 상한 64개는 변경하지 않는다. U 필드(`timestamp`, `kind`, `importance`, `content`)에 content_status와 별도 실행 사실을 추가한 범위는 위 후속 변경을 따른다. evaluator 답·성공 기대값은 넣지 않는다.

큰 trace는 요약·절단하지 않는다. 실행의 남은 token budget이 예상 입력/최대 출력보다 작으면 `budget_exceeded`로 기록하고 호출하지 않는다. 공급자 문맥 한도·응답 실패는 오류이며 정상 답변으로 대체하지 않는다.

## 입력과 실행

질문지는 `configs/survey.json` 기본값 또는 `--questionnaire <json-file>`로 제공한다. 루트 객체는 `questionnaire_id`, `title`, `questions`를 갖는다. 각 질문은 유일한 `id`, `type`(`multiple_choice`, `short_text`, `long_text`), `prompt`를 갖고 객관식만 `options`를 갖는다. `survey --provider` 기본 제공자는 GPU Qwen이며 선택한 실행 제공자를 배치 설문에 그대로 쓰거나 `--survey-provider`로 명시 변경할 수 있다. 자동 provider fallback은 없다.

```sh
python3 -m uxagent survey --run runs/<run-id> --provider gpu --questionnaire configs/survey.json
python3 -m uxagent batch --study configs/study-decathlon-live.json \
  --personas runs/personas/personas.jsonl --provider gpu \
  --questionnaire configs/survey.json
```

단일 실행은 browser run 종료 뒤 호출한다. Batch에서는 먼저 모든 세션 실행을 완료하고 그 다음 각 생성된 run에 설문을 호출한다. 한 설문 실패는 해당 run 결과에만 `survey_status`/오류로 남기고 이후 설문으로 진행한다. 중지 파일이 설문 중 나타나면 나머지는 `skipped_stopped`다.

## 응답과 기록

- 모델은 U JSON (`questionnaire_id`, ordered `answers`, `meta.confidence_overall`)으로 응답한다. 객관식은 제공된 보기 안에 있어야 한다. JSON 파싱·필드·질문 ID·보기 검증이 실패하면 raw 응답을 보존하고 `survey.json` 성공 결과로 쓰지 않는다.
- 기존 `survey.json`은 질문/response 목록을 유지한다. 모델 생성 value/reason, `simulated_self_report`, memory IDs·step 출처를 추가한다.
- 2026-10-19 후속: 재시도가 실패하면 이전 성공의 `survey.json`을 제거한다. 최신 실패 상태·원인은 `survey_result.json`과 summary에 남기고, 이후 성공하면 새 답변 파일을 다시 만든다. D reader의 실패 우선 처리와 별개로 직접 파일 소비자도 오래된 답변을 최신 결과로 읽지 않게 한다.
- `survey_result.json`은 상태, 원본/파싱 응답, 질문지, provider/model, usage, memory 범위와 IDs/seq, 시각, 오류를 보존한다. 민감한 입력/모델 출력은 보내거나 저장하지 않고 generic 오류로 분류한다.
- 설문 시도는 `llm_calls.jsonl`에 module=`survey`로 추가되고 `summary.json`의 공통 request/token/usage/cost 기록을 갱신한다. Qwen 비용은 가격 미확인인 만큼 `null`이며 0으로 바꾸지 않는다.
- 설문 답은 `summary.verification`이나 evaluator 결과를 변경하지 않는다. 사람 검토·인터뷰 경로도 바꾸지 않는다.

## U 원본과 범위

- [U `run_survey`](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/survey.py#L15-L101): system survey prompt, user의 `json.dumps(questionnaire) + "\n" + memory_trace`, invalid JSON의 raw 보존, per-run 출력.
- [U batch 종료 후 설문](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/main/run.py#L71-L104), [U survey prompt](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/shop_prompts/survey.txt).
- 로컬 차이: 결과를 `survey.json`의 기존 질문/응답 형식으로 투영하고 `survey_result.json`에 전체 provenance를 저장한다. run의 공통 예산과 usage를 계속 추적한다. malformed schema·보기 위반은 raw와 오류를 남기되 정상 응답으로 내보내지 않는다.

## 검증 계획과 제한

가짜 provider로 실제 메시지 payload, 제거된 기억·최신 importance, 질문별 다른 응답 저장, 출력 계약, raw fallback, API/예산/빈 입력·민감정보 오류, batch 실행 순서를 검사한다. 실제 GPU 요청 여부는 별도로 기록한다. Mock 테스트는 Qwen 품질 증거가 아니다. 실제 GPU Qwen 설문과 실제 Decathlon 설문 품질은 이슈 구현 테스트와 구분한다.

고정 이슈: [#88](https://github.com/2026-2-1/Persona/issues/88). 선행 Qwen provider는 [PR #91](https://github.com/2026-2-1/Persona/pull/91), survey 선행 행동·memory는 #83–#87이다. 실제 검사 결과와 추가 변경 커밋은 [verification.md](../verification.md)에 남긴다.

2026-10-21 후속: 전체 누적 trace를 모두 분할 요약에 입력하되 Qwen 전송 한도를 넘으면 생성 요약본으로 병합해 설문에 전달한다. 질문지/실제 execution_trace는 그대로 보존하고 요약은 generated_summary로 표시한다. 원본 전체 trace/provenance는 유지하므로 전체 trace 일부를 조용히 잘라 버리지 않는다. 추가 요약도 같은 설문 예산·호출 로그에 포함한다. 이는 U의 전체 원문 단일 요청과 다른 길이 호환 경로다.
