# C 담당 공통 계약·검토 저장·집계 구현 계획

> 작업별 구현과 리뷰는 subagent-driven-development로 진행한다.

## 승인 범위와 제약
기존 Python/Playwright·JSON/JSONL과 단색 UI를 유지한다. P05→P06→P08 순서로 구현하고 각 단계는 독립 테스트·커밋을 남긴다. 로그인·DB·큐·2인 합의·D 담당 검토 입력 UI는 추가하지 않는다. API와 실행 조회/출력에서 판정 상태를 제공한다. 민감 키·runs·개인 문서는 커밋하지 않는다.

## P05 계약
- schemas.py에 CandidateReviewInput(card_id, card_version, reviewer_id, verdict, note)과 CandidateReviewRecord(schema_version, review_id, run_id, 입력 필드, created_at) strict 모델을 추가한다.
- verdict: valid/invalid/deferred/tool_error/environment_error. 미검토는 저장 판정이 아니라 카드 상태 needs_human_review다. 사람 검토 상태는 reviewed 또는 deferred며 UX 후보 유효 판정과 독립 과업 성공은 별도다.
- ID는 기존 issue_id를 카드 로컬 card_id로 재사용. 카드 run_id/card_id + 내용 SHA256 card_version으로 식별한다. review 상태·시각을 hash에 포함하지 않는다. 동일 내용은 같은 버전, 내용 변경 시 과거 검토를 현재에 자동 적용하지 않는다.
- source metadata는 기존 실행 execution_mode/source_kind 유지. legacy 누락은 unknown으로 표시하며 AI/scripted 또는 actual/synthetic를 추정하지 않는다.
- 실제/합성 AI/scripted, 성공/실패/unknown 카드 예시와 판정 레코드 JSON을 docs/examples에 둔다. 기존 출력 consumer 필드는 제거하지 않는다.
- 테스트: 모델 strict/빈 reviewer/불법판정/초과길이, 카드버전 안정성/근거변경, legacy 출처 unknown, 정상 후보0.

## P06 검토 저장
- candidate_reviews.py ReviewStore를 추가. run 하위 candidate_reviews.jsonl에 append-only, fsync, 동시저장 lock, fail-closed 읽기. API는 선택한 카드의 현재 버전과 run identity를 검증 후 저장한다. 활동 중인 실행은 거절한다. symlink/경로 탈출 거절, 중첩 run 지원.
- GET /api/reviews/<run_id>: 기록 목록과 현재 카드 상태. POST /api/reviews/<run_id>: 입력 모델만 허용, 서버 UUID와 UTC 생성. 없는 실행/카드404, 이전버전409, invalid400, origin403. 요청본문/민감내용 오류에 출력하지 않는다. 키/인증URL/개인정보를 검토자와 메모에 쓰지 않도록 안내하며 알려진 secret 패턴/환경값 거절.
- Dashboard.run_detail에서 기존build_cards→리뷰 overlay로 최신 currentversion verdict, 전체 matching history 전달. 사람 판정이 독립verification/관찰/가설을 덮지 않는다. review_summary(total/reviewed/deferred/unreviewed/tool_error/environment_error/valid/invalid) 전달.
- reports JSON/CSV/MD/HTML은 같은 카드 상태/판정/메모 사용, 고정 '사람 검토 전'은 미검토에만 사용. CSV formula와 HTML XSS/키 보호 유지.
- 테스트: restart, 이력보존, invalid ID/version/origin, concurrent append, corruption/symlink, secretreject, 모든출력상태동일. D 입력UI는후속이나 기존카드표시상태는 현재필드소비확인.

## P08 집계
- 기존 requested/rate/median field 보존. 예정 5중 성공2/오류/취소/미실행 포함 분모5, status/verification 두축, 성공0 vs 없음None 구분. scripted는 비교그룹에 배제한다.
- 비용 unknown을0으로바꾸지않고 cost_known_total/cost_known_sessions/cost_unknown_sessions 추가. 요청/입출력토큰 각각 알려진값과 누락수로 구분. recording complete/attempted 및 누락 집계. 중앙값은 성공 세션만, paired delta 아님.
- experiments session에 summary provider_usage/llm_request_count/llm_tokens/metrics와 provider/model 추가보존. 기존기록은unknown; dashboard experiments는조회시현재집계로제공.
- 실패재현tests: planned5success2/scripted배제/zero/unknowncost/partialtokens/missingrecord/cancelregistration; existingcompare_mock와UI회귀.

## 마무리
전체 pytest·doctor·repo/staged·mock 통합, JS 검사, 독립 최종 리뷰. docs contracts/current-state/troubleshooting/verification/tasks와README갱신. 하위3issues및prototypePR등록, CI통과후병합. 실 API나 고객환경 검증을 주장하지 않는다.
