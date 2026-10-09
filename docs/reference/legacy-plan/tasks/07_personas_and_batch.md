# Task 07 — 페르소나 생성과 소규모 배치

상태: 구현 및 mock batch 검증 완료; live 생성 검증 대기 | 선행: 06 | 단계: 논문 구조 확장

## 목표

예시 페르소나와 실험자가 지정한 속성 분포로 여러 페르소나를 만들고, 동일 조건에서 순차 실행한다.

설계 연결: 논문 §3.1 및 Appendix C.1. 표본 크기·스키마·검증 방법은 프로젝트 제안이다.

## 입력·출력

입력: 예시 persona, 생성 수, 속성별 범주와 비율, seed, 공통 과제.

```json
{
  "count": 6,
  "seed": 42,
  "sampling_mode": "quota",
  "attributes": {
    "digital_familiarity": {"낮음": 0.333333, "보통": 0.333333, "높음": 0.333334}
  },
  "fixed_constraints": {"budget_krw": 30000}
}
```

출력: `personas.jsonl`, `generation_manifest.json`. ID·seed·모델·프롬프트 버전·사용량·검증 결과를 저장한다.

## 생성 절차

- [ ] 비율의 합과 음수 여부, count를 검증한다.
- [ ] quota 모드에서는 largest-remainder 방식으로 정수 인원을 배정한다.
- [ ] random 모드에서는 seed를 고정한 난수로 범주를 뽑고 실제 분포를 기록한다.
- [ ] 코드가 먼저 속성을 배정하고 LLM에는 해당 속성을 바꾸지 말도록 요청한다.
- [ ] 배정 속성·예시·공통 제약에 맞는 배경·선호·의도를 생성한다.
- [ ] 기존 결과 중 예시를 seed 기반으로 선택할 수 있게 한다.
- [ ] 생성 결과를 Persona schema로 검증한다.
- [ ] 배정 속성 변경, 예산 모순, 빈 선호, 중복 ID를 탐지한다.
- [ ] 정규화된 내용 hash로 완전 중복을 막는다. 유사 문장은 검토 대상으로만 표시한다.
- [ ] 실패 시 최대 2회 재생성하고 미충족 인원은 명시적으로 보고한다.

여러 속성의 개별 비율만 지정했다고 결합 분포까지 보장하지 않는다. 속성 조합에 제약이 있으면 허용 조합을 별도 입력받는다. 이름·나이만 바꾸고 행동 조건이 같은 결과는 다양성이 충분하다고 보지 않는다.

## 페르소나 작성 원칙

- 실제 개인을 복제하지 않고 가상 프로필을 사용한다.
- 나이·성별로 숙련도나 실수를 자동 결정하지 않는다.
- 디지털 숙련도·가격 민감도처럼 실험에 필요한 특성을 명시한다.
- “낮은 숙련도이므로 반드시 실패” 같은 정답 행동을 프로필에 넣지 않는다.
- 성공 평가가 동일해야 하는 실험에서는 과제 제약을 고정한다.
- 선호 때문에 성공 조건 자체가 달라지면 별도의 task/evaluator로 관리한다.

## 배치 실행

```text
load personas
for persona in personas:
    create fresh browser context
    reset fixture state
    run same study config
    persist independent run summary
write batch summary
```

첫 배치는 3명, 안정화 후 6명으로 늘린다. concurrency=1을 유지한다. 생성 단계 호출과 실행 단계 호출에 각각 상한을 두고 배치 전체 상한도 확인한다.

매 run에서 cookies/localStorage/context를 초기화한다. 테스트 서버에 저장된 상태도 fixture reset으로 초기화한다. 개인화된 서버 상태를 초기화할 수 없으면 run 간 간섭 가능성을 기록한다.

배치를 다시 실행할 때 기존 run을 덮어쓰지 않는다. 이미 완료한 항목을 재실행할지는 manifest로 선택한다. 중간 실패 1개 때문에 나머지 결과를 버리지 않는다.

## 수용 검사

- quota 6명 예시에서 각 숙련도 2명씩 배정된다.
- 동일 seed에서 속성 배정과 예시 선택이 같다. LLM 문장까지 동일하다고 보장하지 않는다.
- 페르소나 schema 위반은 실행 전에 차단된다.
- 이전 run의 검색어나 로그인 상태가 다음 run에 남지 않는다.
- 한 run 오류가 나머지 batch 실행을 중단시키지 않는다. 단, 전체 예산 소진은 batch를 멈춘다.
- 생성 수·성공 생성 수·실행 수·실패 수가 일치하도록 집계된다.

산출물: generator, sampler, persona manifest, 순차 batch runner.

목표 CLI: `python -m uxagent personas --config configs/personas.json`, `python -m uxagent batch --study configs/study.json --personas personas.jsonl`.
