# [phase:1] Brain 모듈 신설과 두 루프 비동기 조율

GitHub: [#43](https://github.com/2026-2-1/Persona/issues/43)

## 범위와 결정

- 실제 AI 실행마다 실행 범위가 분리된 Brain/Fast/Slow를 구성한다. 일반 조건의 Slow 입력에는 persona 배경·선호를 전달하지 않는다.
- Fast가 perception을 저장한 뒤 reflection을, 계획을 저장한 뒤 plan review를 비동기로 예약한다. 단일 worker가 순서대로 처리하고 대기열 상한은 두지 않는다.
- Fast는 Slow 완료를 기다리지 않는다. perception·plan·decision 각 단계가 시작될 때 완료 결과만 회수하며 이미 시작한 프롬프트 입력은 바꾸지 않는다.
- Reflection은 같은 run의 기억 ID와 snapshot 순번이 유효할 때만 다음 단계 메모리에 채택한다.
- Plan review는 같은 observation ID, plan ID, plan version을 가진 decision 시작 전에 완료된 경우에만 해당 decision 문맥에 채택한다. plan을 수정하지 않고 행동은 최신 observation과 ActionExecutor의 검사를 통과해야 한다.
- LLM 요청·토큰 예산은 기본 무제한 설정을 유지한다. 활성 task 한도도 새로 추가하지 않는다.
- 실행이 끝나면 진행 중·대기 작업을 취소하고 각각 취소 상태를 기록한다. 취소·실패·생략을 두 루프 정상 완료로 표시하지 않는다.
- 새/기존 메모리와 작업은 run 경계를 넘지 않는다. #43 구현 당시 5점 고정 정책은 [#40](40-memory-importance.md)의 1~10점 Slow 산정으로 변경됐다.

## 완료 조건

- [x] `brain.py`가 Fast 단계, Slow 예약/결과 채택, 실행별 메모리 상태를 조율한다.
- [x] 일반 실행 설정에서도 두 루프를 구성하고 작업/채택 상태를 기록한다.
- [x] 지연 Slow를 기다리지 않고 stage 경계에서 완료된 결과만 사용한다.
- [x] 낡은 plan review는 폐기하며 현재 plan/행동 대상을 바꾸지 않는다.
- [x] 종료 시 대기/실행 중 작업을 취소하고 작업 누수 없이 상태를 남긴다.
- [x] 동일 프로세스의 서로 다른 실행/조건은 메모리와 작업 결과를 분리한다.

## 검증

- fake provider로 reflection 경계 채택, plan review 일치/stale 검증, 일반 조건 persona 격리, 종료 취소를 재현한다.
- runner mock에서 기본 설정의 Fast/Slow 예약·완료·채택을 확인한다.
- 예산은 무제한(`null`)이며 실제 유료 API는 호출하지 않는다.
