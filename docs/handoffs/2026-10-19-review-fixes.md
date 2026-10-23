# 2026-10-19 코드 검토 5건 수정과 PR 정리

## 병합 후 현재 상태

#101은 `prototype` `9095b3c`에 일반 merge로 병합됐다. #95~#99도 포함돼 병합 처리됐고 6개 원격 브랜치는 삭제했다. 준비 과정에서 password·설문 재시도·취소·GPU 조작 정보 수정을 선행 PR에 반영했으며, 최종 tree는 준비한 #101 `fe94fe3`과 같다. #100은 #101로 대체 종료했다. [병합 후 CI](https://github.com/2026-2-1/Persona/actions/runs/39208715049)는 Ubuntu 574 passed, Windows 569 passed/5 skipped와 doctor·Mock 통과다. 승인 1명과 기존 보호 조건은 유지한다.

아래는 최초 수정 브랜치 작성 시점의 기준·검사·PR 관계다. 아래의 “후속에만 있음”, “원본 head 유지”, “CI 확인 예정”은 준비 당시 기록이며 현재 병합 상태를 뜻하지 않는다. 현재 재현·제한은 [최종 prototype 검증](2026-10-19-prototype-verification.md)을 따른다.

## 기준과 범위

- prototype: `0fad8e59163e8e9559fb1b80562cfce3c6527b05`.
- 최신 U 통합 #99: `f121aaf9ff793a54214d6980a9c7f8fceaa8304c`.
- 기존 D 후속 #100: `ae18a8feffbcba9aac13ba94c9f833088328b0f2`.
- 작업 브랜치: `fix/90-reviewed-regressions`. 동기화 `dc2a473`은 위 두 PR을 merge로 보존하며 기존 커밋을 다시 cherry-pick하지 않았다.
- prototype 대상 후속 PR이다. 선행 #95–#99와 겹쳐 보이는 변경은 기존 코드이며 새 구현으로 계산하지 않는다. 팀원 원본 head·브랜치 보호·승인 조건은 변경하지 않는다.

## 문제별 수정

| 문제 | 변경 | 회귀 |
| --- | --- | --- |
| password 표기 대소문자 | 관찰 HTML/구조화 값 경로 모두 type 정규화 | 3종 표기 × 초기 value/런타임 fill, 실제 DOM 값 보존 |
| Slow 민감 출력 | 전체 응답을 단계/기억 저장 전 검사 | 성찰·생각·중요도 × 패턴/환경값, 부분 저장 금지·usage/출력 |
| 큰 GPU 페이지 조작 정보 | hover 전용 ID, option value/label, 상태/href 보존 | 실제 모델 payload→UAction→호스트 Action, 특수문자·원본 불변 |
| 실제 task 취소 | 최종 결과/요약을 저장하고 writer 종료 뒤 취소 재전파 | 진입·판단·행동·Brain close·최종 캡처·브라우저 종료 6곳 |
| 설문 실패 재시도 | 실패 시 오래된 survey.json 제거, 다음 성공 시 새 답변 생성 | 6종 실패·D 상태·성공 복구 |

각 수정은 별도 `fix:` 커밋이다. 코드·회귀·해당 task/트러블슈팅을 같은 커밋에 둔다. 마지막 설문 커밋은 전체 수정 상태/검증/PR 관계 문서도 갱신한다.

## 기존 PR과 중복 처리

| PR | 이 후속 PR과 관계 | 남는 확인 |
| --- | --- | --- |
| #95 | U parser 선행, password 수정은 이 후속에만 있음 | 원본 단독 병합으로 수정 완료라고 표시하지 않음 |
| #96 | U action 선행을 그대로 보존 | 허용 origin/registry 제한을 다시 넣지 않음 |
| #97 | 설문 생산자 선행, 오래된 성공 파일 제거는 이 후속 | 질문지·누적 trace·usage 계약 유지 |
| #98 | 종료 후 평가 선행, 실제 task 취소 보완은 이 후속 | 취소와 독립 verification 분리 |
| #99 | 최신 Qwen 조각 관찰/짧은 ID 변경 보존 | hover/select 보완을 포함한 통합 검사 필요 |
| #100 | 원래 D 코드 커밋과 다운로드/검토 회귀를 이 후속에 보존 | 새 PR 공개 후 대체 링크를 남기고 #100 종료, 별도 중복 병합 금지 |

새 PR 생성 후 #99에 후속 수정 링크와 위 관계를 남긴다. #100의 원래 검토 이력과 커밋은 보존한다. #36의 팀원 독립 재현·최종 prototype 검증은 완료했다고 주장하지 않으며 이슈를 자동 종료하지 않는다.

검토 범위를 좁히는 명령:

```sh
# 이번 다섯 수정만
git diff dc2a473...fix/90-reviewed-regressions
# 최신 U 통합 이후 D 보완과 다섯 수정
git diff f121aaf...fix/90-reviewed-regressions
```

선행 PR 병합 뒤 prototype을 다시 동기화해 실제 diff와 CI를 확인한다. #95–#99의 개별 head에는 이 후속 수정이 없으므로 기존 수정 요청을 자동 해결 처리하지 않는다.

## 실제 검증과 재현

- Slow 집중 28개, Fast/기억/호출 34개, 취소/비교/지표 30개, 설문/결과/출력 32개 통과.
- 중복을 제거한 로컬 회귀 묶음: **243 passed, 14 deselected**. 제외한 검사는 브라우저/HTTP/격리 SSH agent가 필요한 경로다.
- 신규 Slow·GPU·취소·설문 20개는 수정 전 실패를 확인했다. password는 이전 Chromium 재현 + 동일 소스 확인이며 이번 확장 6개는 로컬 실행 승인 검토의 모델 용량 문제로 실행하지 못했다.
- 로컬 doctor는 Chromium 권한 제한으로 실패했다. 전체 pytest·doctor·Mock 통합은 원격 CI에서 확인한다. 로컬 부분 통과를 전체 통과라고 표시하지 않는다.
- compileall·Node 문법·diff 공백 검사 통과. 최종 repo/staged 검사와 원격 CI는 [검증 기록](../verification.md)과 PR의 현재 head를 기준으로 읽는다.
- 실제 GPU 모델 품질·공개 Decathlon 전체 과업·인간 판단 일치도는 이번 수정 검증에 포함하지 않는다.

```sh
python -m pytest -q tests/test_u_slow.py tests/test_call_evidence.py tests/test_brain_trace.py tests/test_reports.py
python -m pytest -q tests/test_u_fast.py tests/test_u_memory.py tests/test_call_evidence.py -k 'not actual_executor and not fake_http'
python -m pytest -q tests/test_runner_cancellation.py tests/test_experiments.py tests/test_metrics.py tests/test_usage_coverage.py -k 'not runner_preserves and not runner_comparison'
python -m pytest -q tests/test_survey.py tests/test_u_result_views.py tests/test_call_evidence.py tests/test_reports.py
# 브라우저를 실행할 수 있는 로컬 또는 CI
python -m pytest -q
python -m uxagent doctor --study configs/study.json
python -m uxagent run --study configs/study.json --provider mock --headless
```
