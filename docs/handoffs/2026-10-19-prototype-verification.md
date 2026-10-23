# 2026-10-19 prototype 통합 검증과 팀원 재현

## 통합 결과

기준은 `prototype` `9095b3c7896d7080a39d59fb6492251491139fb6`이다. 팀원이 [#101](https://github.com/2026-2-1/Persona/pull/101)을 일반 merge로 병합했고, 선행 #95~#99도 포함돼 병합 처리됐다. 순차 squash로 완료했다고 기록하지 않는다. #100의 기존 D 변경과 코드 검토 수정 5건을 모두 보존했으며, 최종 파일 tree는 준비한 #101 `fe94fe3`과 동일하다. 해당 6개 원격 브랜치는 삭제했다.

필수 승인 1명, Ubuntu/Windows 필수 CI와 최신 대상 브랜치, 대화 해결, 관리자 적용 조건은 유지한다. #36의 팀원 독립 재현은 별도이며 이번 검사로 자동 종료하지 않는다.

## 병합 후 원격 CI

[prototype push 검사](https://github.com/2026-2-1/Persona/actions/runs/39208715049)의 실제 완료 결과다.

| 환경 | 전체 pytest | 나머지 검사 |
| --- | --- | --- |
| Ubuntu / Python 3.11 | 574 passed | repo 검사, doctor, 무료 Mock 통과 |
| Windows / Python 3.13 | 569 passed, 5 skipped | repo 검사, doctor, 무료 Mock 통과 |

Windows 제외 5건은 POSIX authorized_keys/flock/ssh-agent 검사다. 실제 Windows SSH/Slurm 지원을 입증하는 결과로 사용하지 않는다. CI는 Chromium을 설치하고 전체 pytest를 실행하므로 저장·새로고침·네 형식 실제 다운로드 회귀도 포함한다.

## 이번 macOS 검증

실행 코드는 위 prototype과 동일하며 이번 브랜치의 변경은 문서다. Python 3.13.13 / Playwright 1.55.0 / Chromium에서 로컬 HTTP와 브라우저를 허용해 검사했다. doctor는 Chromium available, study_errors 없음이었다.

다음 집중 검사는 **54 passed in 66.99s**였다. 원격 전체 574개와 중복되므로 합산하지 않는다.

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_review_form_browser.py \
  tests/test_review_export_browser.py \
  tests/test_comparison_browser.py \
  tests/test_brain_trace_browser.py \
  tests/test_u_result_views_browser.py \
  tests/test_u_result_views.py \
  tests/test_dashboard_read_failures.py
```

- 판정 5종 저장·재조회, 실패 입력 유지, 중복 제출, 근거 버전 충돌과 이전 판정 분리.
- 자동 갱신·다른 실행 왕복·지연 응답에서 초안과 최신 저장 결과 보존.
- 정상·실패·중지·빈 결과·근거 누락, 부분 측정/실제 0/미확인, 390px 화면.
- 실제 Chromium의 JSON/CSV/Markdown/HTML 다운로드와 동일 카드 필드 대조.
- 최종 관찰 출처, 설문 실패 후 오래된 성공 답변 숨김, 새 U Wonder와 구형 Brain 상태·제거 기억의 출력 일치.

### 새 무료 Mock 실행

`configs/study.json`을 복사해 다른 서버와 겹치지 않는 로컬 fixture 포트와 persona 파일 절대 경로만 지정했다. 과업·30단계·300초·요청/토큰 무제한 설정은 유지했다. 실행 ID는 `20261019T074221-958ea877`이다.

- 독립 `verification=success`, 종료 `termination_reason=max_steps`, 30행동, 기록 30/30(100%). 종료 사유와 성공 판정을 구분했다.
- 단일 Slow worker 시작 1회, 종료 후 active=0 / pending=0, 최종 관찰 `obs-b4cc18c404`. 실제 기록 화면도 예약/진행 0과 종료 취소 1을 표시했다.
- Slow 3,599회 순환과 Mock 호출 로그 7,470회는 무지연 Mock·무제한 설정의 합성 수치다. 실모델 처리량·비용·사용자 효과로 해석하지 않는다. 실제 GPU 파일럿에는 유한 요청/토큰/시간 예산이 필요하다.
- embedding은 `not_configured`다. 이번 실행으로 GPU embedding이나 실제 Qwen 생성 품질을 검증했다고 표시하지 않는다.

### 앱 내 브라우저와 화면 대조

개인 실행 자료와 분리한 합성 `u-review`·구형 `brain-demo` 및 새 Mock을 최신 Dashboard/HTTP handler로 제공했다. `u-review`의 GPU 설문 메타데이터는 합성 fixture이며 실제 GPU 호출 결과가 아니다.

1. 새 Mock의 실제 관찰 PNG·30행동·성공 판정·단계 한도·기록 100%를 확인했다.
2. `u-review`의 `agent_finished + failure`를 확인하고 개선 후보의 최종 평가 근거 버튼이 `obs-final`을 선택하는지 확인했다. 이 합성 자료에는 PNG가 없어 저장된 관찰 화면 없음이 표시된다.
3. 설문의 AI 자기보고 표시·합성 답변·기억/행동 출처를 확인했다. Wonder는 생각 2개·응답 2회·빈 응답 1회이며 생각별 저장 예/아니요가 구분됐다.
4. 별칭 `prototype-qa`, 보류 `deferred`, 쉼표·따옴표·줄바꿈·HTML 문자가 있는 합성 메모를 실제 UI에서 저장했다.
5. 새로고침 후 같은 실행을 다시 선택해 보류 판정·메모·현재 근거 버전 이력 1건이 유지되는지 확인했다. 새로고침 때 미저장 폼 입력이나 선택 실행 복원을 보장하는 검사로 확대하지 않는다.
6. 저장 후 상세 API와 네 형식 응답을 파싱해 아래 필드를 대조했다. 독립 failure와 설문·Wonder·최종 관찰은 유지되고 로컬 호출 원문 marker는 출력에서 제외됐다. 구형 Brain의 예약/진행/완료/생략/실패/취소와 제거 기억 중요도도 API로 대조했다.

| 항목 | 결과 |
| --- | --- |
| 카드 ID | `feature-detail` |
| 근거 버전 | `0505516c02bf19a5323a3d43621bd2cd12093be5d1bf2a3349827a43c1c763fb` |
| 판정·별칭 | `deferred` / `prototype-qa` |
| JSON/CSV/Markdown/HTML | 카드 ID·버전·판정·별칭·메모 일치, 설문 답변·최종 관찰 포함 |
| HTML 메모 | 태그로 실행하지 않고 문자열로 표시 |
| API attachment | 네 형식 모두 Content-Disposition 확인 |

앱 내 브라우저 다운로드 제어는 응답 지연/요소 변경 오류로 저장 파일 경로를 확정하지 못했다. 이 경로의 수동 다운로드 성공으로 기록하지 않는다. 네 형식의 실제 다운로드는 위 Chromium 회귀에서 통과했고, 같은 수동 저장 판정의 네 형식은 API 응답을 대조했다. 인앱 도구의 제한만으로 제품 결함이라고 단정하지 않는다.

화면 캡처·네 형식 결과·대조 JSON은 로컬 ignored `runs/prototype-qa-20261019/`에 보관한다. 원본 실행 기록·개인 파일·스크린샷은 Git에 넣지 않는다.

## 팀원 새 환경 재현

현재 작업을 먼저 보관하고 깨끗한 checkout에서 시작한다. Windows는 `.venv/bin/python` 대신 `.venv/Scripts/python.exe`를 사용하고 `PYTHONPATH=src` 접두어는 생략한다.

```sh
git fetch origin
git switch prototype
git pull --ff-only origin prototype
git rev-parse HEAD
.venv/bin/python -m uxagent doctor --study configs/study.json
.venv/bin/python -m pytest -q tests/test_review_form_browser.py tests/test_review_export_browser.py tests/test_comparison_browser.py tests/test_brain_trace_browser.py tests/test_u_result_views_browser.py tests/test_u_result_views.py tests/test_dashboard_read_failures.py
.venv/bin/python -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect filter
.venv/bin/python -m uxagent dashboard --no-gpu
```

개선 보드에서 방금 만든 합성 필터 결함 후보를 선택해 근거 → 별칭/판정/메모 저장 → 새로고침 → 같은 실행 재선택 → 네 형식 다운로드를 확인한다. 같은 카드 ID·근거 버전·최신 판정·메모·별칭을 대조한다. macOS 임시 검토 저장소는 symlink 없는 실제 경로를 사용한다.

[#36](https://github.com/2026-2-1/Persona/issues/36)에 재현자·OS·Python·커밋·검사 수·화면/출력 결과·남은 오류를 남긴다. AI가 입력한 합성 검토 별칭은 실제 팀원 재현이나 2인 합의를 대신하지 않는다.

## 남은 확인

| 순서 | 검증 | 완료 근거 |
| --- | --- | --- |
| 1 | 팀원의 독립 재현 | 새 환경 결과와 #36 기록 |
| 2 | 실제 Qwen 1회 파일럿 | 유한 예산의 Fast/Slow·embedding·행동·최종 평가·설문 로그 |
| 3 | 큰 페이지·긴 trace·64개 초과 기억 | 실제 context/요약 정보 보존·조작·메모리 갱신 결과 |
| 4 | 실제 중지·SSH 단절·GPU 반환/복구 | 남은 worker·소유 작업·복구 기록 확인 |
| 5 | 인간 판단과의 비교 | 평가셋·2인 판정·합의·통제 실험 |

실제 GPU 할당·Qwen/유료 API·공개 데카트론·기업/실제 사람 데이터는 이번에 호출하거나 사용하지 않았다. GPU health·벡터·작업 반환의 과거 확인은 [GPU 수명주기](../tasks/gpu-dashboard-lifecycle.md), 연구 단계는 [로드맵](../roadmap.md)을 따른다.
