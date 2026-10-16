# [phase:1] 두 루프 LLM 제공자·예산·비교 조건 호환

GitHub: [#46](https://github.com/2026-2-1/Persona/issues/46)

## 구현 기준

- 원본 [neuhai/UXAgent](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd)의 `AgentPolicy.forward`와 `agent/gpt.py`를 기준으로 Fast 인식·계획·행동, 비동기 Slow 성찰·Wonder, 호출별 모델 분기를 대조했다(확인 커밋 `4d3b1f1`). 원본 README와 `pyproject.toml`은 MIT를 표기한다. 소스는 복사하지 않았다.
- 원본은 경량 모델로 인식·피드백·행동, 대형 모델로 계획·성찰·Wonder를 호출한다. 이 프로젝트는 아직 실행 설정에서 생성 모델 하나를 지정하고, #46에서는 실제 단계·제공자·모델 사용을 기록한다. 모델 크기별 별도 선택 설정은 이 이슈의 구현 범위에 포함하지 않는다.

## 범위와 결정

- Fast의 perception·plan·decision과 Slow의 reflection·plan_review·Wonder는 실제 생성 요청을 공통 예산으로 계산한다. Jev는 행동 후보를 `jev-latest`로 선택하고 생성 단계는 설정에서 선택한 Gemini 모델을 사용한다.
- 실행 전에 Jev·Gemini 양쪽 키와 선택 모델의 지원 범위를 확인한다. 현재 embedding은 mock/OpenAI 어댑터에서만 지원하므로 다른 제공자와의 조합은 시작 전에 거부한다.
- 각 호출의 실제 provider/model, 토큰, 비용 미확인 상태, 실패·취소·재시도와 단계 이름을 기록한다. 초기 모델 경로와 최종 예산·종료 사유는 실행 요약에 남긴다.
- 최대 요청/총토큰 기본값 `null`, 최대 행동 30회, 실행 시간 300초는 유지한다. mock 기준 6회 행동에서 기본 생성·Slow 호출 30회였으므로 40회 상한을 복원하지 않는다. 제한값을 지정하면 한도 종류를 구분해 기록한다.
- 일반 AI 비교 조건에서 모든 Fast·Slow·Wonder 생성 입력은 공통 제약과 의도 범위로 축소한다. Wonder 입력은 공통 제약만 사용한다.

## 구현 상태

- [x] Fast/Slow/embedding 호출별 provider/model·사용량·비용·실패 기록 보완.
- [x] 요청/토큰 한도 초과 원인과 설정 모델 경로를 실행 결과에 기록.
- [x] Jev 생성 모델 연결과 실행 전 필수 키·미지원 embedding 조합 검사.
- [x] 일반 조건의 전체 생성 입력 격리와 비교 사전 등록 전 제공자 검사.
- [x] 재시도·예산·Jev·일반 조건 회귀 검사.

## 제한

- 비용표가 없는 모델과 사용량이 없는 실패 호출의 비용은 미확인이다. 로그 비용은 실제 청구액이 아닌 알려진 단가에 따른 추정치다.
- 실제 유료 API 연결·모델 접근 권한·요금 청구는 mock과 fake provider 검사로 검증되지 않는다.
- 실행 시간은 runner의 Fast 단계 경계에서 적용된다. 이미 시작한 동기 브라우저 행동과 제공자 네트워크 요청에는 각자의 timeout이 적용된다.
