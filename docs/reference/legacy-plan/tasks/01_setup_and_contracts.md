# Task 01 — 로컬 환경, 실험 설정, 공통 계약

상태: 구현 및 fixture 검증 완료 | 선행: 없음 | 단계: MVP

## 목표

LLM 없이도 로컬 테스트 페이지를 열고 실험 설정을 읽을 수 있게 만든다. 이후 모듈이 서로 다른 형식의 JSON을 만드는 일을 방지한다.

설계 연결: 논문 §3.4. 아래 설정·스키마는 로컬 구현을 위한 자체 설계다.

## 구현 범위

- Python 가상환경, Playwright, 스키마 검증 라이브러리, CLI.
- 테스트용 쇼핑 페이지 1개: 검색창, 검색 버튼, 필터, 상품 목록, 상세 화면.
- 테스트 페이지는 검색/필터/상세 화면이 한 viewport에 들어오게 구성한다.
- 수동 페르소나 1개, 과제 1개, evaluator 1개.
- 서버 프레임워크나 실제 쇼핑 서비스 연동은 제외한다.

## 체크리스트

- [ ] 지원되는 로컬 OS와 Python 환경을 확인한다. 기존 Python에서 설치 문제가 없으면 버전을 바꾸지 않는다.
- [ ] `pyproject.toml`에 필요한 의존성만 선언한다. 동작 확인 후 정확한 버전을 고정한다.
- [ ] `.env.example`에는 변수명만 두고 실제 키는 넣지 않는다.
- [ ] `runs/`, `.env`, 브라우저 프로필이 git에 포함되지 않게 한다.
- [ ] `python -m uxagent doctor`에서 Python·브라우저 설치·설정 오류를 확인한다.
- [ ] API 키가 없어도 02·03과 mock 실행을 진행할 수 있게 한다.
- [ ] 실험 설정 검증 실패 시 브라우저나 LLM을 실행하기 전에 종료한다.

## 설정 예시

```json
{
  "study_id": "local-shopping-v1",
  "start_url": "http://127.0.0.1:8000/shop.html",
  "task": "3만원 이하의 검은색 가방을 찾아 상세 정보를 확인하세요.",
  "allowed_origins": ["http://127.0.0.1:8000"],
  "persona_file": "configs/persona.json",
  "evaluator_id": "local-bag-detail-v1",
  "viewport": {"width": 1440, "height": 900},
  "observation_policy": "viewport",
  "explicit_scroll": false,
  "max_steps": 30,
  "run_timeout_seconds": 300,
  "max_llm_requests": 40,
  "max_total_tokens": 50000
}
```

`allowed_origins`는 URL 문자열 prefix가 아닌 정규화된 scheme/host/port로 비교한다. 상대 경로는 study 파일 기준으로 해석한다. 예시 URL은 직접 띄울 로컬 fixture 주소다.

## 최소 페르소나

```json
{
  "persona_id": "p001",
  "background": "대학생이며 통학용 가방을 찾고 있다.",
  "digital_familiarity": "보통",
  "preferences": ["가격을 먼저 확인", "검은색 선호"],
  "constraints": {"budget_krw": 30000},
  "intent": "조건에 맞는 가방의 상세 정보를 확인한다."
}
```

## 공통 스키마

| 모델 | 필수 내용 | 소유 task |
|---|---|---|
| StudyConfig | 대상·과제·origin·상한·관찰 정책 | 01 |
| Persona | ID·배경·선호·제약·의도 | 01, 07 |
| Observation | 관찰 ID·탭·URL·HTML·요소·오류 | 02 |
| Action | 행동 종류·관찰 ID·대상·인자 | 03 |
| ActionResult | 실행 여부·오류·전후 URL·시간 | 03 |
| AgentDecision | 관찰 설명·계획·짧은 설명·행동 또는 종료 제안 | 04 |
| StepRecord | observation → decision → action result → next observation 연결 | 05 |
| RunSummary | 종료 사유·검증 결과·카운트·모델 사용량 | 05 |
| MemoryEntry | 내용·종류·출처·생성 순서·검색 점수 | 06 |

처음부터 모든 필드를 구현하지 않는다. 01에서는 StudyConfig와 Persona를 확정하고, 나머지는 각 task에서 구체화한다. 알 수 없는 필드는 오류로 처리하고 `schema_version`을 저장한다.

## evaluator 분리

`local-bag-detail-v1`은 현재 상세 상품의 종류·색·가격과 상세 화면 상태를 fixture의 확인 가능한 상태로 판정한다. 정답 상품 ID, evaluator 코드, 성공용 DOM 속성은 agent observation에서 제거한다. 에이전트는 사용자에게 표시되는 상품 정보만 본다.

## 검증 및 완료 기준

- 정상 설정이 로드되고, 잘못된 URL·음수 제한값·누락 페르소나는 명확한 오류가 난다.
- 새 환경에서 설치 → 브라우저 열기까지의 명령을 개발용 README에 남긴다.
- fixture에서 사람이 검색 → 필터 → 상세 열기를 수행할 수 있다.
- 성공 evaluator가 정답 상세 화면만 성공으로 판정한다.
- API 없이 브라우저를 열고 닫아도 프로세스가 남지 않는다.

산출물: 환경 설정, StudyConfig/Persona 모델, fixture, evaluator 초안, doctor CLI.
