# 2026-10-16 최신 PR 통합·화면·내보내기 검증

검토용 브랜치: `codex/latest-pr-integration-20261015`. 최신 Brain/Slow 생성과 D 검토·내보내기를 한 실행에서 확인하기 위한 통합이다. prototype/main 병합이나 회의 결정, 실제 사용자 연구 결과를 뜻하지 않는다.

## 고정한 PR 범위

| 흐름 | 고정 head | 통합 결과 |
|---|---|---|
| 기존 D/C + 연구 문서 #80 | `c3a4a170328b` | 검토 저장/초안/이력·출처/비교 coverage/출력·연구 문서 유지 |
| 누적 Brain #79 | `1f82379b0139` | #66/#71~#74, #75 생성·소비 본체, #76/#77/#78 본체와 #56 runner 종합 회귀 포함 |
| #78 최신 후속 | `28f912b90a7f` | `ab169b7` 초기 응답 전 입력 편집 보존 + `28f912b` 모델 기본값 대기 테스트 포함 |
| #75 최신 후속 | `9c397b4f94e1` | `dcf272b` 소비 본체 이후 추가된 데이터 갱신 대기 테스트 포함 |

#79 하나만으로 최신 #75/#78 head 전체를 포함하지 않는다. 각각 갈라진 후속 커밋을 별도로 merge했다. 위 head들과 D #68 `e20d7fbdbb3a`가 모두 통합 HEAD의 ancestor인지 확인했다. 통합 코드 커밋은 `168bf71`, `b226029`, `6b3af32`, `0b56d6e`다.

B의 #58/#60/#62는 이번에 합치지 않았다. 원래 기능 PR과 이슈는 닫지 않으며 팀원이 diff·CI·독립 재현을 검토한 뒤 prototype 통합 순서를 결정한다.

## #75와 D 중복 정리

- `brain_trace.py`가 단계·작업·원본 기억·변경·Wonder 추첨을 한 번 검증해 읽는다. 다른 실행 ID, 지원하지 않는 버전, 손상 행, 심볼릭 링크는 경고와 함께 제외한다. #75의 최상위 별칭과 행동 `trace`도 이 검증 자료를 사용한다.
- UI는 D의 `AI 생성·비동기 기록` 패널 하나를 유지한다. #75의 행동별 관찰 → 제안 → 도구 결과 → 재관찰 → 독립 평가를 같은 패널에 연결했다. 원래 관찰 버튼·펼침 유지·D 초안/조회 실패 처리를 보존했다.
- Fast kind와 예약/진행/완료/채택/폐기/생략/실패/취소 8상태를 표시한다. 작업을 펼치면 전체 append 순서 이력을 확인한다. 완료와 채택, 채택과 실제 모델 입력 소비는 서로 다르다.
- Wonder는 생성 가정과 1% 추첨·부모 작업·seed·비당첨을 함께 보존한다. 실제 사용자 증언이나 인간 확률로 해석하지 않는다.
- JSON/Markdown/HTML은 D 카드 ID·버전·판정·메모·이력과 Brain/행동 trace를 함께 보존한다. CSV는 기존 카드 14열을 유지하고 Brain이 있을 때 근거 8열을 추가한다. `record_type`으로 candidate/brain_stage/brain_task_event/memory/memory_change/wonder_draw/brain_warning/step을 구분한다. 모든 행을 후보로 세지 않는다.
- C의 실제 호출 사용량 completeness와 D의 `execution_mode/source_kind`, 최신 Brain의 `brain-3` 프롬프트 버전·협력적 중지를 함께 보존했다. 예산 예약값을 실측으로 표시하지 않는다.

## 실제 검증 결과

| 검사 | 결과 |
|---|---|
| 새 소비 계약 회귀 | 먼저 3개 실패 재현 → 구현 후 통과 |
| 새 390px 화면/네 형식 다운로드 | 먼저 채택 배지 누락 재현 → 구현 후 통과 |
| 전체 pytest | **403 passed in 168.98s** |
| #78 초기화 후속 | 관련 브라우저 2개 통과 |
| #75 마지막 대기 커밋 | 추가 merge 후 해당 브라우저 1개 통과 |
| doctor | Python 3.13.13, Chromium available, study_errors 없음 |
| 기본 검사 | Node 문법·Python compileall·repo/staged 검사·diff 공백 검사 통과 |

처음 전체 검사는 402 passed/1 failed였다. 실패한 기존 #75 테스트가 제거된 중복 패널 제목을 찾고 있었으며, 같은 생성/취소/제거/독립 결과 검사를 단일 패널에 맞춰 갱신한 뒤 403개가 통과했다. 사용량 테스트는 고정 요청 수 7회 대신 fake provider의 실제 시도/응답 카운터와 저장 사용량을 대조한다.

실제 화면 확인은 통합 서버 `http://127.0.0.1:8770/`, 별도 ignored 출력 루트 `runs/latest-pr-integration-20261015`에서 수행했다. 기존 팀원 실행 자료를 수정하지 않았다.

### 무료 Mock: Brain·Slow·출처

실행 `20261015T145603-83f78314`, 로컬 fixture, Mock provider, `wonder_seed=139`.

- 6행동, 독립 판정 `success`, 종료 `verified_success`, Mock 인터페이스 요청 60회.
- 생성 60건: perception/plan/decision 각 6, importance 29, reflection 6, plan_review 6, wonder 1.
- 작업 사건 193건, 원본 기억 30건, 추첨 12회 중 1회 당첨, 읽기 경고 0건.
- 작업별 마지막 상태: completed 47, adopted 6, discarded 7, 나머지 0. 채택은 reflection 5 + Wonder 1이다. plan_review 6건 중 5건은 `stale_context`, 마지막 1건은 `run_finished_unconsumed`로 폐기됐다. 마지막 reflection 1건도 소비 전에 실행이 끝나 폐기됐다.
- 실제 계획 `stage-plan-c6b8d6faaade4c279d98ea46fe54593b`의 관찰 버튼으로 `obs-3fda456cc3` 원본 이미지를 열고 표시 ID가 일치함을 확인했다.
- 실제 계획 검토 `slow-plan_review-df288aa6c148484383b9c604881215ed`를 펼쳐 예약 → 진행 → 완료 → 폐기(`stale_context`) 전체 이력을 확인했다. Wonder를 펼쳐 생성 가정, 부모 작업, seed 139와 12회 당첨/비당첨을 확인했다.

이 Mock 한 건으로 실제 모델의 계획 검토 유용성이나 폐기율 일반값을 주장하지 않는다. `brain_status=completed`는 처리 종료이며 모든 결과의 실제 소비를 뜻하지 않는다. Mock의 미확인 비용도 0원 실측값으로 대체하지 않았다.

### 합성 결함: D 검토 저장·새로고침

실행 `20261015T145630-7a949075`, scripted 필터 결함, 8행동·LLM 0회·독립 `failure/scenario_failed`.

1. 개선 보드의 `feature-6-filters` 후보에서 행동 6의 `obs-3f2c91dbf9`를 열었다. 검정/3만원 이하 조건에도 파랑 19,900원·검정 45,900원 상품이 포함된 합성 결함을 이미지로 확인했다.
2. 별칭 `D-최신통합검증`, 판정 `deferred`, 합성 검증임을 밝힌 메모를 입력했다. 저장 전 다른 Mock 실행으로 이동해 Brain 근거를 확인하고 다시 돌아와 초안이 유지됨을 확인했다. 자동 갱신 중에도 유지됐다.
3. 저장 후 새로고침해 같은 판정·별칭·메모·이력 1건·카드 버전이 유지됨을 확인했다. 독립 과업 판정 failure는 바뀌지 않았다.
4. 카드 버전: `5f8fc6a516c6e760c86b39ce8699d71b4111b8fbfb554ece66f20d46cf22edde`.

### 화면/API/네 형식 출력 대조

- 위 검토 실행의 JSON/CSV/Markdown/HTML에서 카드 ID·버전·판정·별칭·메모·이력이 API/화면과 일치했다. 인앱 브라우저에서 실제 다운로드한 JSON도 동일했다.
- 위 Brain 실행의 JSON 전체 `brain`, CSV의 타입별 전체 JSON 행, Markdown/HTML의 canonical Brain JSON이 상세 API와 일치했다. CSV는 헤더 제외 330행이며 열 수가 일정했다. 행동 `step` 행도 API trace와 일치했다.
- 실제 데모의 네 형식은 서버 응답을 저장해 대조했고, 실제 브라우저 다운로드는 JSON으로 확인했다. 자동 Chromium 회귀에서는 네 형식 링크를 모두 다운로드해 검사했다. 인앱 다운로드 도구가 약 10분 지연돼 나머지 실제 데모 형식에는 같은 도구를 반복하지 않았다.
- 원자료·출력·스크린샷은 ignored 실행 폴더/로컬 임시 폴더에 보관한다. 개인 로그를 저장소에 추가하지 않는다.

## 팀원 재현

```sh
git fetch origin
git switch --track origin/codex/latest-pr-integration-20261015
.venv/bin/python -m uxagent doctor --study configs/study.json
.venv/bin/python -m pytest -q
.venv/bin/python -m uxagent run --study configs/study.json --provider mock --headless
.venv/bin/python -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect filter
.venv/bin/python -m uxagent dashboard --port 8770
```

기존 Python 환경이 없으면 [개발 안내](../development.md)부터 진행한다. Windows는 `.venv/Scripts/python.exe`를 사용한다. 기본 대시보드는 `runs/`를 읽으며 이번 전용 자료를 보려면 `--runs runs/latest-pr-integration-20261015`를 붙인다. 다른 컴퓨터에는 위 실제 run 자료가 없으므로 새로 생성한 ID를 사용한다.

Wonder는 실제 시작된 Slow 작업당 1%라 기본 한 번 실행에서 생성되지 않을 수 있다. 재현 seed 139를 study에 지정할 수 있지만 추첨 기회/스케줄 차이까지 고정되는 것은 아니다. 당첨 유무와 관계없이 추첨 기록·가정 설명을 확인한다.

화면은 실행 기록 → AI 생성·비동기 기록 → 계획의 원본 관찰 → 작업 전체 이력/Wonder 순으로 확인한다. 개선 보드는 후보 → 근거 → 미저장 초안 왕복 → 판정 저장 → 새로고침 → 네 형식 출력 순서로 확인한다. 실패/미확인 비용과 독립 판정이 사람 검토로 덮이지 않는지도 확인한다.

## 남은 논의·작업

1. 통합 PR을 팀원 1명이 독립 재현·리뷰하고 prototype에 반영할 순서를 결정한다. 이미 포함된 원래 PR은 중복 diff가 없도록 base/통합 계획을 정리한다. main은 별도 승인 대상이다.
2. B #58/#60/#62의 실제 사이트/제공자 변경을 별도 통합한다. 현재 Fast 단계 계약과 C 측정/D 검토 회귀를 보존하고 실제 API 결과는 이번 Mock 결과와 분리한다.
3. 연구용 고수준 성찰/계획 검토 off·빈도, importance 분리, 실제 입력 소비 ID·유효 창·폐기율/대기시간 계측을 구현한 뒤 [실험 계획](../research/2026-10-15-slow-loop-experiment-plan.md)을 실행한다. 현재 기본 Fast/Slow 필수와 무제한 대기열/요청·토큰 기본값을 실험 변인으로 임의 변경하지 않았다.
4. 유료 API·실제 사이트·사람 행동/판단 유사성은 이번에 검증하지 않았다. 기업 데이터는 사용자 확인 기준 미수령 0건이다. 멘토에게 시연/출력을 보여드린 뒤 받을 수 있는 자료와 이용 범위를 확인한다.

관련 이슈: [#69 통합](https://github.com/2026-2-1/Persona/issues/69), [#47 소비](https://github.com/2026-2-1/Persona/issues/47), [#36 D-05](https://github.com/2026-2-1/Persona/issues/36). 원래 PR의 승인·닫기나 연구 결과를 이 문서로 대체하지 않는다.
