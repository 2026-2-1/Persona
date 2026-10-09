# Task 03 — Action Space와 브라우저 실행기

상태: 구현 및 fixture 검증 완료 | 선행: 02 | 단계: MVP

## 목표

구조화된 행동을 받아 현재 관찰에서 확인된 대상에만 실행한다. LLM 없이 직접 만든 행동 JSON으로 검증한다.

설계 연결: 논문 §3.3.2 및 Appendix A. 아래 action 이름과 필드, 지원 범위는 자체 API다.

## 행동 계약

```json
{
  "type": "type",
  "observation_id": "obs-0001",
  "tab_id": "tab-1",
  "target_id": "search.query",
  "text": "검은색 가방"
}
```

모든 행동에 관찰 ID와 탭 ID를 요구한다. type별 허용 필드만 받는다. LLM이 만든 CSS/XPath, JavaScript, Python 코드는 실행하지 않는다.

| 행동 | 인자 | 동작 |
|---|---|---|
| click | target_id | 버튼·링크 클릭 |
| type | target_id, text | 입력값을 교체하고 해당 페이지의 입력 이벤트 발생 |
| hover | target_id | 관찰된 hover 후보에 포인터 이동 |
| select | target_id, option_value | 관찰된 native select 옵션 선택 |
| navigate | url | 현재 관찰에 노출된 허용 origin URL로 이동 |
| back | 없음 | 기록상 허용 origin의 이전 페이지로 이동 |
| switch_tab | target_tab_id | 관찰된 탭 활성화 |
| close_tab | target_tab_id | 관찰된 탭 닫기; 마지막 탭은 거부 |

초기 페이지 열기는 runner의 초기화다. 추가 탭은 링크의 정상 동작으로 생기며 관찰 목록에 반영한다. 새 탭을 임의 URL로 만드는 행동은 MVP에 넣지 않는다. `finish`는 브라우저 행동이 아니라 04의 종료 제안이다.

type은 타이핑 속도 시뮬레이션이 아니다. 한글 조합·키보드 중심 UX·커스텀 combobox 조작은 후속 범위다. 검색 fixture에는 클릭 가능한 제출 버튼을 둔다.

## 실행 절차

- [ ] Action schema를 검증한다.
- [ ] 현재 관찰 ID·탭 ID가 일치하는지 확인한다.
- [ ] target이 현재 registry에 있는지 확인한다.
- [ ] action 종류에 맞는 요소인지 확인한다.
- [ ] 연결 상태·disabled·가림·입력 가능 여부를 확인한다.
- [ ] 필요한 경우 대상만 자동 스크롤한다.
- [ ] Playwright의 일반 조작을 사용한다. `force=True`나 JS click으로 실패를 숨기지 않는다.
- [ ] DOM 변경·탭 생성·URL 이동을 처리한다.
- [ ] 제한된 안정화 대기 후 결과를 반환한다. 다음 관찰 발행은 runner가 담당한다.

## 안정화 대기

고정 sleep 하나 또는 무기한 network idle에 의존하지 않는다. 초기 제안은 다음과 같다.

1. navigation이 발생한 경우 문서 로드 상태를 확인한다.
2. 짧은 DOM 변경 없는 구간을 기다리되 최대 3000ms로 제한한다.
3. 광고·분석 요청이 계속되어도 상한을 넘겨 대기하지 않는다.
4. 상한 도달 시 `settled=false`로 반환하고, runner가 재관찰 또는 중단을 결정한다.

이 값은 fixture에서 조정하고 실제 기록에 남긴다. executor의 자동 대기는 사용자 행동 수에 포함하지 않는다.

## 결과 예시

```json
{
  "action_id": "a-0001",
  "observation_id": "obs-0001",
  "ok": true,
  "error": null,
  "url_before": "http://127.0.0.1:8000/shop.html",
  "url_after": "http://127.0.0.1:8000/shop.html",
  "elapsed_ms": 120,
  "settled": true,
  "tab_events": []
}
```

시간은 예시이며 성능 목표가 아니다.

## 오류 코드

`stale_observation`, `target_not_found`, `target_detached`, `not_interactable`, `invalid_option`, `invalid_action`, `navigation_blocked`, `action_timeout`, `unsupported_control`을 구분한다. 오류에는 action ID와 짧은 설명을 포함한다.

잘못된 대상이면 다른 버튼을 추측해서 대신 누르지 않는다. 재관찰 후 LLM이 새 행동을 선택하게 한다. 클릭의 결과가 불명확하면 같은 클릭을 자동 재시도하지 않는다.

## 이동 경계

허용 origin은 초기 이동·navigate·링크 이동·redirect·popup에 적용한다. 문서 navigation을 차단하되 이미지·CSS용 다른 origin 요청까지 일괄 차단하지 않는다. redirect 차단 시 최종 URL과 오류를 기록한다. 실험 중 실제 결제·메시지 전송·파일 업로드는 대상 과제에 포함하지 않는다.

## 수용 검사

- 검색어 입력 → 검색 → 필터 → 상세 확인을 수동 JSON으로 수행한다.
- 오래된 관찰 ID는 부작용 없이 거부된다.
- 삭제된 요소와 가려진 버튼을 강제로 클릭하지 않는다.
- 미관찰 옵션·임의 URL은 거부된다.
- SPA 갱신과 새 탭 링크가 다음 관찰에 반영된다.
- 네트워크가 계속 활동해도 제한 시간 안에 반환한다.

산출물: executor, Action/ActionResult 모델, 탭 관리, 오류 처리.

공식 API 참고: [Playwright actionability](https://playwright.dev/python/docs/actionability).
