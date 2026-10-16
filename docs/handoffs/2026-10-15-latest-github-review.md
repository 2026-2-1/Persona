# 최신 GitHub 변경과 연구 문서 반영 확인

조회 기준: **2026-10-15 23:27 KST**의 PR/이슈/branch 및 고정 head. 이 기록은 원격 변경 확인이며 새 코드를 로컬에 통합하거나 테스트한 기록이 아니다.

## 기준을 세 가지로 구분

| 범위 | commit | 의미 |
|---|---|---|
| 원격 prototype | `9323df5c2b6617d084017d491ff8cb239b11a087` | PR #26까지 반영. 아래 새 PR들은 조회 당시 모두 open/미병합 |
| 어제 독립 검증한 A+D preview | `5ca409d3663951466d8bceb25f91c0d2968c3a24`, PR #70 | 324개 검사·실제 무료 시연의 기준. 새 원격 생성기 전체를 포함하지 않음 |
| 최신 누적 기능 PR #79 | `1f82379b0139d080162003076f2a3538c779e163` | Brain/Slow/검색/보호·통합 검사 포함. 작성자 보고와 코드 읽기 확인, 이번 독립 실행은 하지 않음 |

문서 PR #80 최초 head `de4eee0`는 preview와 #63 후속 수정 중심이어서 #66/#71~#79의 최신 구현을 충분히 반영하지 못했다. 이번 정정에서 **preview 미포함, 원격 PR 구현 포함, 통합·독립 검증 대기**를 구분한다.

## 새 PR 목록과 반영 내용

| PR / 고정 head | 원격 변경 | 연구·회의 문서에 반영할 점 |
|---|---|---|
| [#66](https://github.com/2026-2-1/Persona/pull/66) `e09b7db` | 별도 성찰·계획 검토, 단일 worker/상한 없는 대기열, 이 단계에서는 중요도 5 고정 | 해당 기능을 저장소 전체의 미구현으로 쓰지 않음. 중요도 정책은 이후 #76을 기준으로 읽음 |
| [#71](https://github.com/2026-2-1/Persona/pull/71) `65636a3` | 실행별 Brain, 단계 경계에서 Slow 결과 회수·채택/폐기, 현재 계획 검토 조건 | 새 조율 구조를 재구현할 과업 대신 통합/연구 조건 확장으로 분류 |
| [#72](https://github.com/2026-2-1/Persona/pull/72) `ab6cf6b` | 관찰→Brain→실행→재관찰→평가, 협력적 stopping/cancelled | D 중지 상태·근거 보존 계약과 함께 통합 검토 |
| [#73](https://github.com/2026-2-1/Persona/pull/73) `bf2d2bf` | 실제 시작한 Slow 작업당 1% persona-only Wonder, 기본 활성 | 주 실험에서 명시적으로 `enable_wonder=false`, 추첨·생성 상태 구분 |
| [#74](https://github.com/2026-2-1/Persona/pull/74) `e23d924` | 단계별 실제 provider/model·예산 결과, 일반 조건 문맥 격리 | 실제 모델 경로·usage 기록 재사용. 유료 API/과금 검증과 구분 |
| [#75](https://github.com/2026-2-1/Persona/pull/75) `9c397b4` | Brain·Wonder·출처·CSV 타입을 읽는 별도 화면/보고서 변경 | D #68과 중복 구현/같은 파일 변경. 어느 계약을 통합할지 먼저 합의 |
| [#76](https://github.com/2026-2-1/Persona/pull/76) `1354c8b` | 미산정 null→Slow worker의 1~10 점수, 늦은 결과·예산 상태 | 현재 중요도 5 고정이 아님. 검토 off에서도 같은 중요도 산정을 유지할 독립 예약 경로 필요 |
| [#77](https://github.com/2026-2-1/Persona/pull/77) `ef3e628` | 실제 Fast/Slow 검색 profile·종류 가중치·필수 현재 관찰 포함 | Slow 전체 snapshot만 전달한다고 쓰지 않음. 최신 구현 기준선을 실험 조건과 구분 |
| [#78](https://github.com/2026-2-1/Persona/pull/78) `28f912b` | 현재 단계/최근 과업 기억/미산정/Slow snapshot 보호·embedding 제거, 후속 화면 초기화 회귀 수정 | 보존 규칙을 조건마다 동일하게 고정. 후속 커밋 누락 없이 통합 |
| [#79](https://github.com/2026-2-1/Persona/pull/79) `1f82379` | N=10/64 runner 통합 회귀, 출처·예산·최근 행동 분리 | 작성자 273개 통과 보고를 어제 D 324개와 합산하거나 독립 검증으로 쓰지 않음 |

위 PR 번호는 통합 순서의 단서이며 각 prototype diff에는 선행 변경이 포함된다. #53은 이전 draft, #76은 이후 누적 계열의 중요도 복원 작업이다. 같은 이슈의 두 PR을 중복 병합하지 않는다. B #58/#60/#62의 실제 연결/데카트론 흐름도 최종 통합 시 별도 보존한다.

## 코드에서 직접 확인한 연구상의 차이

아래 코드는 #79 고정 head 기준이다.

1. [schemas.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/schemas.py): `enable_slow_loop=False` 입력도 validator가 True로 바꾼다. `reflection_every_actions=5` 필드는 남아 있지만 [runner.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/runner.py)는 perception/plan 뒤 매 차례 예약한다. 두 설정 이름만 바꿔서는 off/5차례 실험이 되지 않는다.
2. [slow_loop.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/slow_loop.py): 단일 worker가 고수준 작업 전에 `_score_pending`을 수행한다. off 조건에서 중요도만 동일하게 유지하려면 성찰과 분리된 연구용 산정 예약이 필요하다. snapshot은 **실제 작업 시작 시** deep copy하고 예약 시 순번과 구분한다.
3. [memory.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/memory.py): I/Q/R은 Fast 1/3씩, Slow `(0.2,0.2,0.6)`. Fast 계획/행동에는 별도 기억 종류 가중치가 있다. 이 실제 기준선과 제안한 관련성/중요도 우선 실험은 다르다. 종류 가중치를 조건마다 같이 바꾸지 않는다.
4. [brain.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/brain.py): plan_review는 decision 경계에서 observation·plan ID·version이 모두 일치할 때만 채택된다. 다른 경계에서 회수되면 폐기될 수 있다. 팀 대화의 “다음 새 계획에 이전 계획 검토 반영”과 같은 동작이라고 쓰지 않는다.
5. `adopted`는 결과를 기억/경계 후보로 채택한 사건이다. Runner가 실제 입력을 만드는 `with_boundary_memories`에는 top-k 제한이 있다. 채택 사건만으로 모든 결과가 실제 요청에 전달됐다고 계산하지 말고 단계의 `source_memory_ids`와 원본 생성 ID를 연결한다.
6. [experiments.py](https://github.com/2026-2-1/Persona/blob/1f82379b0139d080162003076f2a3538c779e163/src/uxagent/experiments.py): 새 계열은 일반/persona 비교의 Slow 거절을 제거하고 문맥 격리를 적용했다. 연구용 빈도/검색 조건 manifest와 5반복 실행은 여전히 별도 확장이 필요하다.

## D 통합에서 새로 확인한 계약 차이

- 새 `BrainTaskEvent`는 Fast kind와 `adopted/discarded`까지 **8상태**를 허용한다. 어제 D `brain_trace.py`는 6상태/Slow kind만 허용하므로 새 Fast·채택/폐기 행을 제외하는 분기가 있다. 원격 코드와 로컬 허용 목록을 정적으로 대조한 결과이며 새 로그의 실제 브라우저 통합을 검증하지 않았다.
- #75는 Wonder 추첨·새 기록 소비를 별도로 구현했다. D #68과 하나의 화면/내보내기 계약을 선택하고 초안 보존·조회 실패·사람 이력·네 형식 일치를 함께 회귀해야 한다.
- 최신 생성기의 run.json과 D의 실행 출처 필드도 통합 시 맞춰야 한다. 새 코드 존재만으로 D의 `execution_mode/source_kind` 계약과 C의 측정 누락 표시가 보존됐다고 가정하지 않는다.
- `completed` 뒤 `adopted/discarded`가 추가될 수 있으므로 완료율은 마지막 상태 수만으로 계산하지 않는다. task ID별 전체 사건에서 완료/채택/실제 입력 포함을 각각 센다.

## 최신 head 하나로 모두 포함되지 않는 부분

[#78 head 28f912b 대 #79 head 1f82379](https://github.com/2026-2-1/Persona/compare/1f82379b0139d080162003076f2a3538c779e163...28f912b90a7f089b3ea612a3e00cf7ee55f10171)는 서로 분기돼 있다. #78에 후속 2커밋, #79에 종합 검사 1커밋이 각각 있다. #78 후속에는 app.js 초기화 처리와 마법사 테스트가 포함된다. 따라서 #79 번호가 가장 크다고 #78 최신 수정까지 전부 포함한다고 보지 않는다.

## 실제 수행한 확인과 제한

- 로그인된 GitHub 도구로 최근 PR 35개·이슈 20개와 prototype SHA를 조회했다. 연결 검색 결과만으로 전체 목록을 판단하지 않았다.
- #66/#71~#79의 본문·상태·head를 읽고, #79의 Brain/Runner/Slow/Memory/Schema/비교 코드를 확인했다. #78/#79 비교와 #78 마지막 커밋의 패치를 확인했다.
- 이 결과를 실험 계획·회의 안건·제출 구조/구현 범위에 반영한다. 기업 데이터 미수령 0건은 그대로다.
- 최신 기능 PR은 미병합이며 새 전체 조합의 pytest·Mock·실제 화면·유료 API·사람 실험을 이번 문서 정정에서 수행하지 않았다. 작성자의 개별 검사 보고와 어제 독립 preview 검증을 구분한다.

관련: [실험 계획](../research/2026-10-15-slow-loop-experiment-plan.md), [회의 안건](../meetings/2026-10-15-research-and-data-agenda.md), [제출 초안](../research/2026-10-15-project-submission-draft.md).
