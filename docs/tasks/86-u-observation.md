# #86 U DOM parser 기반 화면 관찰

이슈: [#86 화면 관찰을 U DOM parser·semantic ID 방식으로 변경](https://github.com/2026-2-1/Persona/issues/86). 원본 비교 기준은 [U parser.js](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/parser/parser.js), [U initscript.js](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/parser/initscript.js), [U environment observation](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/env.py#L1136-L1214)다.

## 변경 전후

| 이전 관찰 | 현재 #86 구현 |
|---|---|
| viewport 내 후보 CSS 요소 추출 | U parser의 visibility·blacklist·빈 컨트롤 보존·허용 속성·flatten 적용 |
| `data-uxagent-id` + 로컬 별칭 ID | 원본/정리 DOM에 U `parser-semantic-id`; 실행기는 그 ID로 원본 요소를 찾음 |
| semantic HTML을 100요소/12,000자로 실제 절단 | 관찰 전체를 모델에 전달하고 길이·요소 수와 기존 설정 한도 초과를 CaptureInfo에 기록 |
| 초기 DOM 로드 대기와 MutationObserver quiet | context init-script의 XHR/fetch 활동 추적, 제한 시간 network idle, DOM quiet |
| JSON/PNG 자료 | 기존 `observations/<id>.json/.png` 위치와 스키마 유지, capture policy를 `u-dom-parser`로 표시 |

## 로컬 어댑터와 알려진 차이

- U의 parser.js는 원본과 정리 DOM에 의미 ID를 함께 붙인다. 로컬 registry locator는 `[parser-semantic-id="..."]`만 사용하고 가장 최근 관찰 registry만 ActionExecutor에 게시한다. 페이지가 rerender되어 ID가 사라진 요소는 detached/미발견 오류가 난다.
- U `clickable_elements` 문자열 ID와 input/select 객체를 로컬 `ElementInfo` 계약에 매핑한다. Fast의 U payload에는 기존처럼 유효 target ID를 사용한다. #83에 기록한 U 입력/선택 후보 목록의 원본 동작은 이 변경에서 별도로 고치지 않는다.
- 한국어는 U JavaScript `\w` 기반 slug에서 ASCII 단어 문자가 없어 `item`, `item1`처럼 번호가 붙을 수 있다. ID는 실행 중 최신 관찰에만 유효하며 사람이 읽는 표시 이름은 접근 가능한 label/aria-label/placeholder/text를 보존한다.
- 비밀번호 입력의 값 속성은 관찰 HTML에서 제외하고 구조화된 요소 값은 `[redacted]`로 표시한다. 보안상 필요한 이 차이는 U 동작을 그대로 복제하지 않는다.
- 기존 max text/elements 값은 더는 조용한 절단 기준이 아니다. `CaptureInfo.observed_text_chars`, `observed_element_count`, 두 configured limit과 `limits_exceeded`에 남는다. Qwen 컨텍스트 초과는 모델 요청 오류로 드러나며 일부 관찰을 U와 같다고 가장하지 않는다.
- 실제 공개 데카트론에서 이 한도 오류가 확인되어 GPU Qwen의 큰 화면 **모델 입력**만 보이는 문구와 조작 대상 목록으로 압축한다. 원본 observation와 registry는 그대로 저장하고, 모델용 ID는 실행 전 원본으로 복원한다. 다른 제공자는 U HTML 입력을 유지한다. 압축된 Qwen 관찰은 U 전체 HTML 설명과 동일하지 않다.
- init-script는 hover 이벤트 대상 표시와 XHR/fetch 추적에 한정한다. 브라우저 context/viewport/headed 옵션, 탭·JSON/PNG·세션 종료 경계는 기존 Python/Playwright 구현이다. U의 지속 브라우저 세션·수동 로그인·녹화·Flask/Vue는 포함하지 않는다.
- U parser가 제거하는 iframe/canvas 등은 지원으로 주장하지 않는다. iframe/canvas 태그 이름은 unsupported metadata로 기록한다.

## 검증 범위

`tests/test_u_observation.py`는 빈 input/contenteditable, select option/current value, 같은 이름의 중복 ID, 스크롤 가능한 아래 요소와 숨김 요소, parser 재실행, 원본 DOM locator, password redaction, network 대기 timeout과 hover/fetch 추적을 검사한다. 기존 action/runner 검증도 U ID 변경에 맞춰 실행한다.

합성 fixture 검사는 공개 Decathlon 검증이 아니다. 실제 Decathlon에서는 검색창·상품/필터 요소의 관찰과 의미 ID만 확인하고, 상품 검색·필터·구매 과업 성공 판정으로 확대하지 않는다. 실제 검사 결과는 [verification.md](../verification.md)에 기록한다.
