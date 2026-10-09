# Task 02 — Observation Space

상태: 구현 및 fixture 검증 완료 | 선행: 01 | 단계: MVP

## 목표

현재 페이지에서 에이전트가 읽어도 되는 정보와 실행 가능한 대상을 추출한다. 이 단계에서는 LLM을 호출하지 않는다.

설계 연결: 논문 §3.3.1, Fig. 3. JSON 형식과 실패 처리는 아래 자체 계약을 따른다.

## 인터페이스

```python
async def observe(session, previous_error=None) -> Observation: ...
```

한 번의 호출로 현재 active tab의 관찰과 해당 관찰에 묶인 내부 target registry를 만든다. registry에는 실제 요소 참조를 보관하되 LLM에는 제공하지 않는다.

## 관찰 JSON 예시

```json
{
  "schema_version": "1.0",
  "observation_id": "obs-0001",
  "tab_id": "tab-1",
  "url": "http://127.0.0.1:8000/shop.html",
  "title": "테스트 상점",
  "html": "<main><input semantic-id=\"search.query\" placeholder=\"상품 검색\"><button semantic-id=\"search.submit\">검색</button></main>",
  "clickable_elements": [{"id": "search.submit", "role": "button", "name": "검색", "enabled": true}],
  "input_elements": [{"id": "search.query", "role": "textbox", "name": "상품 검색", "value": ""}],
  "hoverable_elements": [],
  "select_elements": [],
  "tabs": [{"id": "tab-1", "title": "테스트 상점", "active": true}],
  "error": null,
  "capture": {
    "policy": "viewport", "truncated": false,
    "omitted_element_count": 0,
    "screenshot_path": "observations/obs-0001.png"
  }
}
```

## 추출 규칙

- [ ] script/style/meta, 주석, 숨겨진 입력값, evaluator 전용 속성을 제거한다.
- [ ] CSS 숨김, zero-size, viewport 밖의 요소를 관찰에서 제외한다.
- [ ] viewport와 조금이라도 교차하는 요소는 포함하고 실제 조작 가능성은 executor가 다시 검사한다.
- [ ] 제목·문단·레이블·리스트·버튼·링크·입력 요소의 의미 구조를 보존한다.
- [ ] 의미 없는 wrapper만 축약한다. 텍스트를 부모·자식에서 중복 수집하지 않는다.
- [ ] 텍스트·aria label·연결된 label·placeholder로 이름을 구하고, 없으면 tag/role 기반 이름을 쓴다.
- [ ] native control, 링크, button/link role, onclick, pointer cursor를 클릭 후보로 탐지한다.
- [ ] 입력값·checked·selected·disabled·focus를 현재 DOM 상태에서 읽는다.
- [ ] password 값은 마스킹한다. 전체 raw HTML이나 localStorage를 모델 입력에 넣지 않는다.
- [ ] 이벤트 등록 계측으로 hover 후보를 찾는 기능은 1차에는 생략 가능하다. 이때 CSS/알려진 메뉴 후보만 탐지하며 완전한 탐지를 주장하지 않는다.

## semantic ID

- 이름을 짧은 slug로 만들고 landmark/section 범위와 결합한다.
- 같은 이름은 관찰 내 충돌 없는 suffix로 구분한다.
- 같은 DOM 노드는 가능하면 같은 ID를 유지한다. 재렌더링으로 다른 노드가 되면 동일성을 보장하지 않는다.
- ID만으로 권한을 주지 않고 `(observation_id, tab_id, element_id)`로 검증한다.
- 새 관찰을 발행하면 이전 실행 registry는 폐기한다. 과거 JSON은 로그에 남긴다.
- 의미와 관계없는 화면 전체 순번만을 영구 식별자로 사용하지 않는다.

## viewport와 스크롤 정책

기본 모드는 현재 viewport만 관찰하고 독립 scroll을 제공하지 않는다. 관찰 후 레이아웃이 변한 대상은 실행 직전 자동으로 화면 안에 맞출 수 있다. 하지만 **처음부터 화면 아래에 있던 미관찰 요소를 자동으로 발견할 수는 없다.** 따라서 첫 fixture는 한 화면 안에서 완료하도록 만든다.

긴 페이지를 지원할 때 선택할 후속 변경은 두 가지다. 어느 것을 쓰든 config·로그에 남겨 baseline과 혼합하지 않는다.

1. `viewport_with_scroll`: 명시적 scroll 추가. 논문 기본 행동 집합에 대한 프로젝트 확장.
2. `rendered_document`: 화면 밖의 렌더링 요소도 노출. viewport 관찰에 대한 프로젝트 변경이며 인간이 보지 않은 정보가 제공될 수 있음.

둘 다 이번 MVP 필수는 아니다. 정확한 원본 구현의 off-screen 기준은 논문만으로 확정하지 않는다.

## 분량·캡처

- 최대 텍스트 12000자, 대상 요소 100개를 시작값으로 한다. 설정 가능하게 만든다.
- 원래 읽기 순서로 제한하고 누락 수·truncated를 기록한다. 과제에 맞는 정답만 골라 노출하지 않는다.
- viewport PNG와 JSON을 같은 관찰 ID로 저장한다. PNG 저장이 모델에 이미지를 보냈다는 뜻은 아니다.
- 수집 중 URL/DOM 세대가 바뀌면 최대 1회 재시도하고, 그래도 불안정하면 capture 오류를 반환한다.
- iframe 내부·canvas 조작·복잡한 shadow DOM은 미지원으로 표시한다. 빈 페이지라고 단정하지 않는다.

## 수용 검사

| 사례 | 기대 결과 |
|---|---|
| 숨겨진 정답 텍스트 | 관찰에 없음 |
| 같은 이름의 버튼 2개 | 서로 다른 ID |
| 검색어 입력 후 재관찰 | 실제 value 반영 |
| 동적 목록 재렌더링 | 새 registry, 과거 ID 실행 불가 |
| disabled 버튼 | 상태가 표시되며 executor가 거부 가능 |
| 화면 아래 요소 | 기본 모드에서 제외 |
| 분량 제한 초과 | 누락 표시와 일관된 ID 목록 |

완료: `python -m uxagent observe --study configs/study.json`으로 JSON/PNG를 만들고 위 사례를 확인한다.

산출물: observation 모듈, DOM 추출 스크립트, target registry, Observation 모델.
