# 2026-10-18 D/U 통합 검증

관련: [D-05 #36](https://github.com/2026-2-1/Persona/issues/36), [Brain 소비 #47](https://github.com/2026-2-1/Persona/issues/47), [U 최종 호환 #90](https://github.com/2026-2-1/Persona/issues/90). 검증은 합성 fixture·Mock/Fake 응답이며 실제 사람/기업 데이터나 GPU 모델 성능 실험이 아니다.

## 검증 대상과 원격 상태

- 원격 `prototype`: `0fad8e59163e8e9559fb1b80562cfce3c6527b05`. #91–#94 squash 병합 완료. 로컬 기준 저장소 `6a45`의 tree가 이 prototype tree와 동일함을 확인했다.
- 후속 브랜치: `codex/d-u-integration-verification-20261018`. #99 원본 head에서 prototype을 동기화한 `1dbcf93`은 파일 tree 변경 없이 squash 계보의 충돌만 해소했다. 팀원 원본 브랜치를 변경하지 않았다.
- 아래 U PR은 모두 Draft이며 기존 head와 CI 성공 상태가 유지됐다. CI 성공이 알려진 경계 오류의 해결이나 병합 승인을 뜻하지 않는다.

| PR | 원본 head | 상태/선행 조건 |
|---|---|---|
| [#95](https://github.com/2026-2-1/Persona/pull/95) | `94b689030e9069f8bf7a9ddda2523ca2e9f7eb89` | 수정 요청: password type 대소문자 처리에서 값 노출 재현 |
| [#96](https://github.com/2026-2-1/Persona/pull/96) | `7506b9bb611f45ca1d5405c50b766bb091e2aba7` | #95 선행 수정·통합 대기 |
| [#97](https://github.com/2026-2-1/Persona/pull/97) | `053c5bcc61d14b782b48b7fe07fe26637f7f0ca6` | 수정 요청: 실패한 재시도 후 survey.json에 이전 성공 답변 잔존 |
| [#98](https://github.com/2026-2-1/Persona/pull/98) | `edc0264f99559b4a907c05a3e139539bd867b5a9` | 선행 U PR 수정·통합 대기 |
| [#99](https://github.com/2026-2-1/Persona/pull/99) | `aafea5ab8b8d53fcac12a440157d2a55f2c64626` | 수정 요청. CLI 원문 복사·D 설문/Wonder 소비는 이 후속 브랜치에서 보완. 원본 PR head에는 아직 미반영 |

이 후속은 선행 U 코드를 포함한 통합 미리보기다. 선행 PR의 생산 모듈 문제를 해결했다고 표시하지 않으며, 이 브랜치도 선행 수정 전 prototype에 바로 병합하지 않는다. 필수 리뷰/CI 보호 조건을 변경하지 않았다.

## D 보완

1. **최종 독립 평가:** 종료 사유·독립 판정·관찰 ID/시각을 표시한다. 최종 실패 후보는 별도의 최종 관찰 버튼을 제공하며 그 근거가 바뀌면 카드 버전이 바뀐다. 기존 scripted 행동 근거는 유지한다.
2. **사후 설문:** 완료된 질문지/답변을 검증하고 AI 자기보고임을 표시한다. 모델 원문/프롬프트는 내보내지 않는다. 설문의 기억/행동 출처는 전체 입력 trace 범위이며 답변별 인과 증거로 주장하지 않는다. 최신 실패/손상 결과는 이전 성공 파일로 대체하지 않는다. 구형 survey.json은 생성 출처 미확인으로 표시한다.
3. **U Wonder:** 매 반복 정책과 실제 thoughts 수·빈 응답을 분리한다. `kind=thought` 저장 이력을 연결한다. 구형 추첨 기록만 1% 설명을 사용하며 stage-only 저장 이력도 호환한다.
4. **출력:** 네 형식에서 같은 카드·최종 평가·설문·Wonder projection을 사용한다. CLI review HTML에도 공통 공개 호출 projection을 적용한다. 원본 JSONL 파일은 변경하지 않는다.
5. **다운로드:** 내보내기에 attachment 파일 응답을 명시한다. 수정 전 앱 내 브라우저 HTML download timeout을 재현했고, 수정 후 실제 HTML 다운로드를 확인했다.
6. **기존 화면:** 최종 평가·설문이 없는 실행은 빈 새 패널을 숨긴다. 기존 desktop 배치와 390px 검토·출력 회귀를 확인한다.

## 실제 실행과 화면 결과

### 현재 prototype 기준

- 합성 필터 결함 실행 `20261018T105758-e225f9f1`: 8행동, `scenario_failed`, 독립 `failure`, 기록 8/8.
- 후보 `feature-6-filters`, 행동 6 관찰 `obs-f52efaf0ca`. 검정/3만원 이하 필터를 적용해도 파랑 19,900원과 검정 45,900원 상품이 남는 화면을 확인했다.
- 테스트 별칭 `D-통합검증`, `valid`와 합성 검증 메모 저장 → 새로고침 → 이력 1건 유지. 독립 failure는 그대로다.
- 근거 버전 `3a1d668ec15e4484e39538f26f1e6607371c2619ae5bf3ea258edc151ef04963`.
- 기준 서버에서 실제 JSON 다운로드를 대조했다. 이 실행 폴더를 U 후속 서버에도 읽어 같은 검토 버전/판정/이력을 유지하고 네 형식을 모두 앱 내 브라우저에서 다운로드·대조했다. 원본 기록은 보존했다.

### U 후속 미리보기

- 실제 runner/Playwright에 결정적 Fake 제공자를 연결한 `u-d-integration-demo`. 파랑 상품을 연 뒤 종료하도록 한 합성 실패 예시다. 유료 모델/GPU 호출은 없다.
- 독립 `failure`, 종료 `agent_finished`, 최종 관찰 `obs-d94b925fcb`, 사유 `detail_product_mismatch`. AI 종료와 과업 성공을 구분했다.
- Brain/Slow: Slow worker 1회 시작, 16 cycles, Wonder 응답 16회/빈 응답 15회/실제 생각 2개, 두 생각 모두 기억 저장. 종료 시 진행 작업 1건은 cancelled, active 0이었다. 이 수치는 합성 응답의 기능 검증이며 연구 효과 지표가 아니다.
- 사후 설문을 실제 create_survey 경로로 생성하고 화면에서 질문/답변·출처·Mock 제공자·AI 자기보고 표시를 확인했다.
- 후보 `feature-detail` → 최종 평가 근거 버튼 → 실제 PNG 확인 → 테스트 별칭 `D-통합검증`, `deferred` 저장 → 새로고침 → 현재 이력 1건을 확인했다.
- 근거 버전 `5ebb9c7e9831550a4c17738f070de529529bd9cba7eeb5dc781e9adbc3ca7399`.
- JSON 카드 전체와 조회 카드가 동일했다. CSV의 실행/카드 ID·버전·판정·메모·별칭·상태, Markdown/HTML의 동일 필드를 대조했다. 네 형식 모두 같은 최종 관찰과 설문 답변을 포함했다. 독립 failure는 변경되지 않았다.
- 앱 내 브라우저에서 JSON/CSV/Markdown/HTML 모두 실제 다운로드했다. HTML은 attachment 보완 후 재시도에서 성공했다.

다른 실행 왕복 및 자동 갱신 뒤에도 테스트 별칭/판정/미저장 메모가 유지됨을 직접 확인했다. 새로고침으로 해당 테스트 초안만 지우고 저장된 이력은 유지했다.

로컬 원본/화면/비교 결과는 `/private/tmp/persona-d-u-20261018/`, 실제 다운로드는 사용자 Downloads에 남겨 두었다. 원본 실행·PNG·모델 프롬프트를 저장소에 추가하지 않는다.

## 검사

실패 재현을 먼저 추가했다. 초기 U 소비 검사 6개 실패, UI 연결 검사 2개 실패, null 설문 fallback 및 attachment 헤더 누락 실패를 각각 확인했다. 첫 전체 실행은 543 passed/3 failed였다. 기존 desktop 배치 2건은 빈 새 패널 숨김으로, 구형 Wonder 저장 1건은 stage-only 구버전 호환으로 수정했다. 수정 직후 desktop·U 흐름·attachment 집중 검사 5개가 통과했다.

최종 전체 검사는 **547 passed in 344.24s**였다. doctor는 Python 3.13.13 / Playwright 1.55.0 / Chromium available, study_errors 없음이다. compileall·Node 문법·repo 검사·공백 검사도 통과했다. doctor·기본 Mock의 상세 결과는 [검증 기록](../verification.md)의 이번 날짜 항목을 기준으로 한다. Windows/Ubuntu 원격 CI는 PR의 실제 결과를 따로 확인한다. 기본 무료 Mock `20261018T111848-04cbdb13`은 max_steps/30행동/독립 success/기록 30/30이었다. 무제한 Slow 반복을 포함한 Mock 요청 8,016회를 기록했으며 실제 유료 모델의 성능·비용을 측정한 수치는 아니다.

## 팀원 재현과 남은 완료 조건

새 venv에서는 저장소 루트에서 아래를 실행한다. Windows는 `.venv/bin/python`을 `.venv/Scripts/python.exe`로 바꾼다. 기존 설치 venv를 다른 checkout에서 공유한다면 `PYTHONPATH=src`를 지정해 오래된 editable 경로를 사용하지 않도록 한다.

```sh
.venv/bin/python -m pytest -q tests/test_u_result_views.py tests/test_u_result_views_browser.py tests/test_review_export_browser.py tests/test_review_form_browser.py tests/test_brain_trace_browser.py
.venv/bin/python -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect filter
.venv/bin/python -m uxagent dashboard --no-gpu
```

1. 합성 필터 결함 후보의 행동 6 화면을 확인하고 테스트 별칭/판정/메모를 저장한다.
2. 다른 실행 왕복/자동 갱신 중 미저장 초안, 새로고침 후 서버 저장 이력을 확인한다.
3. 네 형식 다운로드에서 같은 카드 ID/버전/최신 판정/메모를 대조한다. 설문 없는 실행은 없음을 유지한다.
4. 실제 U 실행 기록이 있으면 최종 평가 화면과 종료 사유, 설문 AI 자기보고, Wonder의 빈 응답/실제 생각 수를 확인한다.
5. 재현자·OS·커밋·결과를 #36 또는 후속 PR에 남긴다. 실제 GPU/공개 사이트 결과는 Mock 검증과 구분한다.

- [x] D 코드에서 U 결과 소비 보완 및 합성 기록 두 종류의 저장·새로고침·네 형식 출력 대조
- [x] 원본 U PR head·CI·수정 요청 상태 확인
- [ ] 팀원 독립 재현/리뷰
- [ ] #95/#97 생산 모듈 수정과 U 선행 PR 순차 통합
- [ ] 최종 prototype 커밋에서 CI 및 같은 저장·출력 흐름 재확인

#36은 위 남은 조건을 확인한 뒤 완료 처리한다. 새로운 연구 기능이나 GPU 품질 실험을 D 완료 조건에 추가하지 않았다.
