# 공통 DOM 요소 문맥

## 요구와 변경

가격 Min/Max만 구별하는 보완을 모든 관찰 컨트롤로 확장한다. 이름이 같은 버튼도 어느 상품·폼·메뉴의 버튼인지 모델이 구별하도록 한다. 사이트별 필터 목록이나 AI 요약을 추가하지 않고 DOM 구조에서 공통 정보를 추출한다.

1. 기존 U parser가 실행 가능한 semantic ID를 만든다.
2. `parser/element_context.js`가 같은 DOM에서 이름과 근거, 소속 그룹, 상태와 관계를 추출한다.
3. `Observation`에 요소별 `context`, 공유 `context_groups`, 실행 불가 컨트롤의 `context_only_elements`를 저장한다.
4. `dom_context.py`가 사용 중인 대상만 선택하고 그룹 정의를 한 번씩 전달한다. 짧은 모델 ID와 원본 ID의 매핑을 유지한다.
5. 계획·행동·검색 보조 판단·팝업 판단에 해당 문맥을 전달한다. 요약기는 `<element_context>`를 바꾸지 않는다.
6. 입력이 크면 기존 계층별 대상 선택을 사용한다. 구역 선택용 이름은 앞뒤 미리보기임을 표시하고, 최종 선택 구역에는 전체 추출 이름과 그룹 정의를 제공한다.

## 추출 정보

| 정보 | 근거와 처리 |
|---|---|
| 이름 | aria-labelledby → aria-label → label을 우선하며 텍스트·대체 텍스트·placeholder·title 등을 사용한다. 인접 텍스트와 기술적 name은 nearby로 구별한다. |
| 소속 | form/fieldset/legend, article/반복 카드, 목록·메뉴, dialog, tablist/tabpanel, 표·행 등 조상 구조와 제목을 공유 그룹으로 표현한다. |
| 제약 | type, min/max/step, 길이 제한, required, readonly, disabled, autocomplete 등 DOM 속성을 보존한다. |
| 상태 | 선택·체크·펼침·누름·현재 위치·오류·로딩 관련 ARIA 속성과 비활성 옵션을 전달한다. |
| 관계 | aria-controls/owns, 설명·오류 참조, 표 열 제목을 전달한다. 확인할 수 없는 관계는 unresolved로 표시한다. |
| 불확실성 | 이름이 없는 요소는 unknown으로 유지한다. 반복 카드에 여러 경쟁 제목이 있으면 대표 의미를 강제로 정하지 않는다. |

반복 div 카드는 형제 구조와 제목/링크/이미지·컨트롤 존재로 추정한다. 이 소속과 인접 이름은 DOM 기반 추정이며 페이지 작성자의 명시적 의미와 구별해야 한다. Min/Max 의미는 보존하되 모든 과업의 조건 해석을 하드코딩하지 않는다.

비활성 컨트롤은 정보로만 제공하며 실행 registry에 새 대상을 만들지 않는다. 비밀번호 값은 가린다. 팝업 판단에서는 가장 가까운 dialog 위의 배경 그룹과 외부 관계를 제외한다. 기존 검색창 식별과 행동 실행 정책은 유지한다.

## 검증과 재실행

```sh
python3 -m pytest -q tests/test_dom_context.py tests/test_u_observation.py tests/test_target_selection.py tests/test_interaction_flows.py
python3 scripts/verify_dom_context_sites.py --output runs/private/dom-context-live-check
```

라이브 검사는 공개 페이지를 읽고 원본 DOM·관찰·스크린샷·모델 입력을 지정한 `runs/` 아래에 저장한다. 로그인·폼 제출·구매를 하지 않는다. 명시적 DOM 라벨 일치, 그룹/대상 참조 무결성, 모델 입력 보존을 확인한다. 실제 Fast 입력 검사·대상 선택은 모델 응답을 모의해 검증하며 실제 Qwen 요청은 하지 않는다.

2026-10-22 실제 수집에서 **서로 다른 13개 사이트**가 통과했다: [Decathlon](https://www.decathlon.co.kr/), [IKEA](https://www.ikea.com/kr/ko/), [Wikipedia](https://www.wikipedia.org/), [Python](https://www.python.org/), [PyPI](https://pypi.org/), [MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input), [GitHub](https://github.com/python/cpython), [GOV.UK](https://www.gov.uk/), [NHS](https://www.nhs.uk/), [Mozilla](https://www.mozilla.org/en-US/), [OpenStreetMap](https://www.openstreetmap.org/), [Apple](https://www.apple.com/kr/), [Kernel](https://www.kernel.org/).

[W3C](https://www.w3.org/WAI/tutorials/forms/)는 HTTP403 challenge, [GNU](https://www.gnu.org/)는 네트워크 중단으로 제외했다. 로컬 상세 기록은 `runs/private/dom-context-live-2026-10-22-verified/report.md`다. 원본 자료는 Git에 넣지 않는다.

## 남은 한계

이는 모든 사이트의 의미 해석이나 Qwen 자율 과업 성공을 보장하는 검사가 아니다. iframe·닫힌 shadow DOM·canvas·아직 렌더링하지 않은 가상 목록에는 별도 관찰이 필요하다. 제목이 없거나 모호한 구조는 unknown으로 남는다. 그룹 정보 증가로 대상 선택 호출이 늘 수 있으며 실제 지연 개선량은 측정하지 않았다. 실제 Qwen의 가격·날짜·사이즈 선택 및 과업 성공은 후속 검증 범위다.
