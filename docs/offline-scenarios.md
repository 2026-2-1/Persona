# API 없는 과업 점검

API 키 없이 사전 정의한 브라우저 단계와 독립 코드 평가를 실행한다. `provider=scenario`, `execution_mode=scripted`, `condition=scenario`로 기록하며 LLM 요청·토큰은 0이다. 페르소나 생성·AI 성능·사람 행동 재현 실험으로 해석하지 않는다. 기존 무료 Mock 데모는 `shop.html` 전용으로 별도 유지한다.

## 대시보드

`API 없는 과업 점검 → 다음`에서 시나리오와 합성 재현 결함을 선택하고 다음 단계의 실행 확인 후 `점검 실행`을 누른다. API 연결이나 페르소나 생성 없이 실행 기록으로 이동한다. 종료 후 결과·단계별 전후 화면·URL·개선 보드·JSON/CSV/Markdown/HTML 내보내기를 확인한다. 종료 메시지와 과업 성공 판정은 별개다.

| 합성 시나리오 | config | 확인 범위 |
|---|---|---|
| 검색 → 필터 → 상품 상세 | `decathlon-flow.json` | 가방 검색, 검정·3만원 이하, 상세 필수 정보 |
| 빈 결과 안내와 검색어 변경 | `decathlon-empty.json` | 없는 검색어 안내, 가방으로 교체 후 결과 |
| 필터 초기화와 결과 복원 | `decathlon-reset.json` | 선택·적용 상태 해제와 결과 복원 |
| 스크롤 후 픽업 안내 확인 | `decathlon-scroll.json` | 화면 밖으로 이동한 뒤 안내 조작·표시 |

합성 상품은 실제 데카트론의 상품·가격·재고가 아니다. `search`, `filter`, `reset`, `detail` 결함을 주입해 검색 불일치·조건 미반영·초기화 실패·상세 누락을 재현한다. 결함과 관련 없는 시나리오가 통과해도 해당 결함을 검증한 결과가 아니다.

```powershell
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-empty.json
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-reset.json --defect reset
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect detail
```

`--headed`로 브라우저를 표시하며 `--output`으로 기록 위치를 지정할 수 있다. CLI 종료 코드만으로 성공을 판단하지 말고 `summary.json`의 `verification`, `termination_reason`, `evaluator.feature_checks`를 함께 읽는다. `scenario_failed`도 CLI가 정상 종료할 수 있다.

## 실제 공개 데카트론의 부분 점검

대시보드의 `공개 데카트론 부분 점검 (실험)`은 `decathlon-live-results.json`을 사용한다. 사전 지정 `https://www.decathlon.co.kr/search?query=러닝화`에서 시작하며 아래 세 체크만 평가한다.

- `search_results`: URL 검색어와 표시된 카드 이름의 검색어 포함 여부. 입력창과 폼 제출은 검사하지 않는다.
- `filters_price`: URL의 가격 상한이 80000이고 표시된 카드의 가격이 상한 이내인지 확인한다.
- `detail_basic`: 관찰된 모델 8926930 상세의 이름 `남성 러닝화 킵코어`와 가격 상한을 확인한다.

```powershell
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-live-results.json --output runs/live-check
```

2026-10-11 00:38 KST 실행 `20261010T153846-0c0a13c5`는 위 부분 범위에서 success로 종료했다. 가격 체크의 표시 카드 12개와 상세 79,900원을 확인했으며 6개 행동·LLM 요청 0을 기록했다. 홈페이지부터 제출하는 실험 config `decathlon-live.json`의 별도 실행 `20261010T153352-0871d10a`는 URL 검색어를 확인하지 못해 unknown이었다. 순차 한글 입력·Space/Enter 보조 단계를 넣었다는 사실은 해결 완료를 뜻하지 않는다. 상세는 [검증 기록](verification.md)을 따른다.

`configs/decathlon_live_profile.json`은 관찰된 DOM 속성 기반의 부분 프로필이다. scope는 표시 카드 또는 상세 이름·가격이며 전체 카탈로그·의미 관련성·색상·사이즈·용도·재고·픽업은 미검증이다. 검색어를 포함하는 가방 카드도 조건을 만족할 수 있다. 사이트 변경·상품 미노출·중복/누락 값은 미확인으로 남긴다. live에는 합성 결함을 주입하지 않는다.

## 행동과 기록 계약

시나리오의 selector는 신뢰된 로컬 config에서만 받는다. 최신 observation registry의 관찰된 후보와 `element.matches`로 교집합을 구하며 전역 DOM에서 화면 밖 목표를 임의 실행하지 않는다. 같은 selector가 여러 후보에 맞으면 명시적 `target_index`가 필요하다. 가격 popup의 Min/Max가 화면 밖이면 scroll 후 새 관찰을 먼저 받는다. keypress는 Enter/Escape/Tab/ArrowUp/ArrowDown/Space로 제한하고 scroll은 한 번에 ±900px 이내다.

검사는 DOM·URL 기반 `pass/fail/unknown/unsupported`와 observation/step 연결을 남긴다. 숨긴 앱 상태나 모델의 성공 선언은 정답으로 사용하지 않는다. 로그인·장바구니·구매·결제와 민감정보 입력은 이 읽기 전용 실행 범위에 포함하지 않는다.

실패 체크는 `unmet_checkpoint`, 행동/관찰 오류는 `system_error_candidate` 카드로 구분한다. 카드에는 실제 체크 단계·이유·근거·개선 제안·완료 조건을 연결하며 사람 검토 전 후보다. 스크립트의 반복 클릭을 AI 혼란으로 해석하지 않는다. `runs/` 원자료·PNG는 저장소에 추가하지 않는다.
