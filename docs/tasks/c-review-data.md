# C 담당 P05·P06·P08

작업 이슈: [P05 #27](https://github.com/2026-2-1/Persona/issues/27), [P06 #28](https://github.com/2026-2-1/Persona/issues/28), [P08 #29](https://github.com/2026-2-1/Persona/issues/29).

[구현 계획](../plans/2026-10-11-c-review-data.md)에 따라 공통 계약 → 검토 저장 → 집계 검증 순서로 진행한다. 기존 Python/Playwright/JSONL과 위저드를 유지한다.

## 역할 인계

- A: valid/invalid/deferred/tool_error/environment_error 판정 기준과 메모를 확정한다. 사람 판정은 독립 과업 verification과 별도다.
- B: 실제 모델의 summary/provider_usage/metrics와 실행 기록을 전달한다. 비용 미확인은 null이다.
- C: 카드버전·검토 저장/조회·같은 출력 상태·예정 분모를 보장한다.
- D: GET 실행/검토 응답과 예시를 사용해 검토 입력 UI를 별도 개발한다. 이번 C 작업은 저장 API와 상태 소비만 추가한다.

## 완료 조건

- [ ] P05: 기존 issue_id를 보존한 카드 ID/버전, strict 검토 모델, 출처/결과 예시.
- [ ] P06: append-only 검토, 재시작/동시 요청/경로·버전 검증, 조회·네 출력·기존 상태 표시 일치.
- [ ] P08: 성공2/예정5, scripted 배제, 비용/토큰/기록 누락과 성공 중앙값 검증.
- [ ] 전체 회귀·repo·doctor·mock·독립 리뷰·CI와 prototype 병합.

## 이번 범위 밖

로그인·공개 다중 사용자 서비스·2인 독립 합의·고유 문제 중복 병합·환경 실험·실제 API 검증·검토 입력 폼은 별도 범위다. 한 검토자의 유효 판정은 확정 UX 결함이나 실제 사용자 증언을 뜻하지 않는다.

## 로컬 API 확인 (D 연결 전)

카드가 있는 완료 실행 ID를 사용한다. 아래는 로컬 테스트용 검토자 별칭과 메모이며 인증정보를 넣지 않는다.

```powershell
$taskRunId = '완료-실행-ID'
$taskReviewUrl = "http://127.0.0.1:8765/api/reviews/$taskRunId"
$taskDetail = Invoke-RestMethod $taskReviewUrl
$taskCard = $taskDetail.cards[0]
$taskReviewBody = @{
    card_id = $taskCard.card_id
    card_version = $taskCard.card_version
    reviewer_id = 'reviewer-1'
    verdict = 'deferred'
    note = '원인 확인 후 재검토'
} | ConvertTo-Json
Invoke-RestMethod $taskReviewUrl -Method Post -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($taskReviewBody))
Invoke-RestMethod $taskReviewUrl
```

201은 판정 저장, 404는 없는 실행/카드, 409는 실행 중/카드 버전 변경, 400은 입력 불일치, 500은 손상 이력 등 조회 불가다. 성공을 받지 못했을 때 저장됐다고 표시하지 않는다. 카드 버전 변경 시 재조회 후 실제 근거를 다시 검토한다. 이력은 해당 runs 하위 candidate_reviews.jsonl에만 저장되며 Git에서 제외된다.
