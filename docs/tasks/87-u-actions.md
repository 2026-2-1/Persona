#87 U 행동 집합·페이지 프롬프트·접근 정책

## 기준

- U 코드 기준: [neuhai/UXAgent `4d3b1f1`](https://github.com/neuhai/UXAgent/tree/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd)
- [U step dispatch](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/env.py#L629-L748), [U 행동 메서드](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/executor/env.py#L754-L1021), [U action prompt](https://github.com/neuhai/UXAgent/blob/4d3b1f1c1fef93c5e2ea7d104153ea164ba1acbd/src/simulated_web_agent/agent/shop_prompts/action.txt)
- 관련: [#83 Fast](83-u-fast.md), [#86 DOM parser](86-u-observation.md), [#89 종료 후 평가](https://github.com/2026-2-1/Persona/issues/89), [GitHub issue #87](https://github.com/2026-2-1/Persona/issues/87).

## 변경 전 → 변경 후

| 변경 전 | 변경 후 |
| --- | --- |
| `click/type/hover/select/keypress/scroll/navigate/back/switch_tab/close_tab` | U의 전체 dispatcher action 17종을 모델 응답과 실행기에 연결 |
| 최신 observation ID, 활성 tab ID, registry membership, capability, 옵션 membership을 실행 허가에 사용 | ActionExecutor가 U semantic ID를 현재 DOM에서 조회하고 Playwright 동작 결과를 기록 |
| configured origin 외 이동과 top-document redirect를 route abort | AI 경로에서 브라우저 origin 차단 제거. 서로 다른 origin과 redirect를 실행 가능 |
| 전역 키·임의 키 조합, raw type, 좌표 클릭 미지원 | U의 key_press(선택적 target), raw_type, mouse_click 지원 |
| study의 scroll opt-in 및 ±900px 상한 | U의 up/down/left/right + amount로 키보드 스크롤 수행 |
| start_url origin이 allowed_origins에 포함되어야 함 | allowed_origins는 구 study 호환 입력이고 U AI 실행의 접근 허가 정책이 아님 |

## U 동작 계약

지원하는 model proposal:

```text
click, mouse_click, type, raw_type, scroll, hover, select, clear,
key_press, goto_url, back, forward, refresh,
new_tab, switch_tab, close_tab, terminate
```

- `click`, `type`, `hover`, `select`, `clear`: `target`은 parser semantic ID다. U와 같이 현재 DOM의 `[parser-semantic-id]` 값을 찾아 locator를 실행한다. 현재 observation 목록에 있었는지, 해당 capability가 목록에 있었는지 검사하지 않는다.
- `type`: `target`, `text`, 선택적 `enter`; `enter=true`면 fill 후 Enter.
- `mouse_click`: `at_x`, `at_y`에 페이지 마우스를 클릭한다. `raw_type`: 현재 focus에 키 입력을 보낸다.
- `scroll`: `direction`은 up/down/left/right, `amount`만큼 방향키를 세 번씩 누른다. U와 같이 설정 기반 opt-in/±900px 제한을 적용하지 않는다.
- `key_press`: `key`를 페이지 전역에 보내거나, 선택한 `target`을 focus한 뒤 보낸다. 브라우저/Playwright가 지원하지 않는 조합은 실행 오류다.
- `goto_url`, `back`, `forward`, `refresh`는 현재 탭에서 동작한다. `new_tab`은 선택 URL로 탭을 만들며 URL은 생략할 수 있다.
- U의 숫자 tab ID(0-based)는 현재 `Observation.tabs` 순서에서 BrowserSession의 문자열 ID로 변환한다. 실제로 열려 있지 않은 tab은 `target_not_found`다.
- `terminate`는 ActionExecutor에 보내지 않고 U proposal을 기존 완료 신호로 변환한다. 독립 성공/실패 판정 변경은 #89다.

## 제거한 AI 실행 정책과 유지한 실패 의미

AI 경로에서 제거한 실행 허가 정책은 다음과 같다.

- current observation/tab ID와 active-page ID 일치 검사
- 최신 TargetRegistry/registry membership 검사
- target capability·관찰된 URL·select option membership 검사
- `allowed_origins` 비교와 BrowserSession top-document route block
- scroll opt-in 및 U 글로벌 key 제한
- password, readonly, custom aria-disabled control 전용 차단 분기

JSON 필드 누락·unknown action·현재 DOM에 없는 semantic ID·열려 있지 않은 tab·Playwright timeout/interaction failure는 성공으로 바꾸지 않는다. 오류는 `ActionResult.error`에 남아 runner가 후속 관찰과 함께 기록한다. 허용 제한을 제거하는 것은 API URL, local server bind, 파일 경로, API key redaction, 실행 예산/timeout, 사람이 보낸 중지 요구를 제거하는 것이 아니다.

기존 사전 정의 scripted scenario는 AI execution path와 별도다. `offline.py`가 configured origin 및 read-only login/purchase/personal-data 정책을 유지한다. 오래된 `allowed_origins` study 필드는 읽을 수 있지만 `runner`/`cli`의 AI browsing route를 제한하지 않는다.

## 변경 파일과 통합

- `schemas.py`: UAction과 내부 Action 필드/dispatch를 확장하고 오래된 `keypress`, bounded `scroll_y` 입력은 기존 로그/script 호환으로 유지한다.
- `fast_loop.py`: U proposal을 내부 Action으로 일대일 변환하고 local action prompt의 origin/capability 제한 문구를 U 동작에 맞춘다.
- `actions.py`: registry 승인 단계를 제거하고 semantic ID를 현재 DOM에서 조회한다. Playwright 오류는 그대로 실패로 반환한다.
- `browser.py`, `runner.py`, `cli.py`: AI 경로의 allowed-origin route guard와 start-origin membership 선행 검사를 제거한다.
- `offline.py`: scripted scenario의 origin guard를 그 실행 경로 내부에 분리 유지한다.
- `AGENTS.md`, contracts, architecture, current-state, troubleshooting, verification 및 README의 실행 계약을 갱신한다.

## 회귀 시나리오

- 서로 다른 로컬 HTTP origin 두 개로 goto URL redirect, back/forward/refresh를 검증한다. 외부 공개 사이트를 호출하지 않는다.
- new tab / switch / close 및 tab-index 어댑터를 검증한다.
- 임의 key 조합·전역 키, type+Enter, raw type, clear, 방향/큰 amount scroll, 좌표 클릭을 검증한다.
- 실행 전에 observation에 없던 semantic ID 및 오래된 observation ID를 실행 허가 조건으로 거절하지 않는다. 현재 DOM target 자체가 없거나 탭이 닫힌 경우 도구 오류를 검증한다.
- unknown action과 필수 JSON field 오류는 성공으로 변환하지 않는다.
- GPU URL 제한, server bind, 파일 경로 보호, secret redaction, stop/timeout과 offline scripted origin/read-only policy 회귀를 유지한다.

## 검증 기록

실제 구현 PR의 고정 커밋, 실패 재현 전후, 전체/집중 테스트, wheel 및 저장소 검사는 [verification.md](../verification.md)의 `#87` 항목에 남긴다. 실제 GPU Qwen 생성이나 실제 데카트론 과업 성공을 이 로컬 행동 dispatcher 검사로 대체하지 않는다.
