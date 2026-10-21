# 모델 연결·JSON 오류 운영 매뉴얼

기준: 2026-10-20, Python/Playwright 실행기와 GPU `persona-qwen`. 모델·프롬프트·파서·연결·실행기 변경 때 이 문서를 읽고 마지막의 검증 기록을 갱신한다. 증상만 가리는 보정 대신 실패 요청과 실제 응답을 근거로 수정한다. 외부 네트워크·Slurm·모델 생성의 무오류를 보장하는 문서는 아니다. 장애 감지·복구·중단·재발 검사의 기준이다.

## 1. 먼저 구분할 것

| 증상 | 의미 | 첫 확인 | 대응 |
|---|---|---|---|
| `provider_transient:ConnectionRefusedError` | 로컬 모델 포트가 연결을 받지 않음. JSON 응답을 받은 것이 아님 | 채팅·임베딩 health, SSH master, Slurm 작업 | 소유 할당이 RUNNING이면 터널 복구. 할당이 끝났으면 대시보드 정상 종료 후 재시작 |
| `model_connection_error` | GPU 전송 오류가 실행 단계에 기록됨 | summary의 last_error, health, gpu_connection | 연결 경로부터 해결. 프롬프트나 JSON을 수정하지 않음 |
| `provider_http_400: Prompt too long` | 서버의 입력 문맥 한도 초과 | 해당 호출 stage·입력 길이·서버 한도 | 공통 PromptGuard·prompt_summary 기록·보호 필드 크기를 확인. 원본을 자르지 않고 조각 요약과 병합 |
| `Expecting ',' delimiter`, `JSONDecodeError` | 받은 응답 자체가 JSON 문법을 위반 | 비공개 llm_calls의 원본 response, 출력 한도·잘림 여부 | 아래 JSON 처리 규칙 적용. 내부 내용을 추측해 임의 복구하지 않음 |
| `GPU perception chunk must contain a nonempty observation` | 관찰 문자열이 전부 비었거나 계약을 충족하지 못함 | 실제 observations 배열·타입·내용 | 비어 있지 않은 여러 관찰은 모두 순서대로 사용. 전부 비었으면 오류 유지 |
| `ValidationError` | JSON 문법은 맞지만 단계별 필드·타입이 다름 | schemas.py의 해당 U 모델과 실제 응답 비교 | 해당 단계의 스키마·프롬프트·소비자를 함께 확인 |
| `CancelledError`와 `run_timeout` | 실행 시간 한도로 진행 중 요청을 취소했을 수 있음 | summary의 termination_reason과 호출 시각 | GPU 경합·Fast/Slow 요청 수·지연 확인. JSON 오류나 성공으로 바꾸지 않음 |
| HTTP 429/5xx 또는 Timeout | 제공자 제한·서버 오류·대기 초과 | HTTP 코드, 요청 시각, 응답 유무 | 제한된 재시도만 사용. 서버가 이미 요청을 받았을 수 있음을 고려 |
| 대시보드 네트워크 요청만 계속됨 | 상태 폴링일 수도 있음 | 새 step/action·브라우저 URL·호출 완료 기록 | 폴링을 행동 진행 증거로 해석하지 않음 |

연결·시스템 오류를 실제 사이트 UX 문제로 판단하지 않는다. AI의 terminate, 실행 종료 사유, 종료 후 독립 성공·실패 판정은 별도다.

## 2. 정상 실행 순서

1. 프로젝트 루트에서 `python3 -m uxagent dashboard`를 실행한다. 비공개 GPU 설정이 있으면 SSH 인증 → 단일 Slurm 할당 → 채팅/임베딩 포트 전달 → health·임베딩 벡터 probe → 짧은 채팅 확인 뒤 HTTP 화면을 제공한다.
2. 터미널의 `UXAgent dashboard: http://127.0.0.1:8765` 출력을 확인한다. 시작 중에는 브라우저의 이전 탭만 보고 모델 준비 완료로 판단하지 않는다.
3. `/api/state`의 `providers.gpu=true`, `gpu_connection.status=connected`를 확인한다. 화면이 HTTP 200이어도 GPU 모델은 별도로 끊겼을 수 있다.
4. 소수 페르소나·짧은 단계부터 시험하고 호출 로그·실제 행동·최종 판정을 확인한 뒤 범위를 늘린다. 연결 성공은 전체 과업 성공의 증거가 아니다.
5. 종료는 대시보드 터미널의 Ctrl+C. 소유 Slurm 작업 반환 확인 메시지까지 기다린다. 브라우저 탭 닫기는 서버/GPU 종료가 아니다.

인증은 기존 OS 키체인/SSH 키 설정을 사용한다. 비밀번호·개인 키·토큰을 이 문서, JSON 설정, `.env`, 로그, 이슈에 넣지 않는다. 상세 설정은 [GPU 수명주기](tasks/gpu-dashboard-lifecycle.md)를 따른다.

### 모델 health 직접 확인

자동 GPU 모드의 기본 로컬 포트는 채팅8001, 임베딩8002다. 설정을 바꿨다면 아래처럼 비공개 설정에서 포트만 읽는다. 이 검사는 생성 요청이 아니다.

```sh
python3 - <<'PY'
import json
import urllib.request
from pathlib import Path

c = json.loads(Path('runs/private/gpu-session.json').read_text())
ports = [('chat', c.get('local_port', 8001))]
if c.get('embedding_model'):
    ports.append(('embedding', c.get('embedding_local_port', 8002)))
for name, port in ports:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3) as response:
        d = json.load(response)
        print(name, response.status, {k: d.get(k) for k in ('status', 'model', 'device')})
PY
```

채팅은 HTTP200/status=ok/model=persona-qwen이어야 한다. 임베딩은 설정한 모델명과 cuda 장치여야 한다. 실제 벡터 검사는 시작 시 수행하며 health200만으로 벡터 응답까지 검증했다고 쓰지 않는다. 수동 터널 모드는 `PERSONA_QWEN_API_URL`의 로컬 포트를 확인한다.

## 3. 터널·GPU 장애 처리

구현: `gpu_session.py`, `monitor.py`, `llm.py`, `fast_loop.py`, `runner.py`.

- 대시보드는 5초 간격으로 health를 검사한다. 생성 요청은 보내지 않는다. 자동 GPU 세션의 health가 실패하면 저장된 인증으로 로그인 master를 확인/복구하고 Slurm의 사용자·고유 작업 이름·ID·RUNNING·노드를 검증한 뒤 사라진 계산 노드 터널을 복구한다. 기존 할당을 재사용한다.
- batch/compare 실행 직전에도 health와 복구를 확인한다. 복구 실패 시 새 실행 파일·브라우저를 만들기 전에 요청을 거부한다. 과거의 연결 성공 기록만으로 실행을 허용하지 않는다.
- `providers.gpu`는 현재 연결 상태를 반영한다. 세부 상태는 `/api/state`의 `gpu_connection`에 있다. 연결된 모델명 이력과 실제 연결 상태를 혼동하지 않는다.
- Fast의 GPU 일시 오류 재시도는 최대4회다. 최초 시도 포함5회, 대기는 2·4·4·4초이며 예산·실행 시간 한도가 우선한다. 다른 제공자는 기존2회 재시도를 유지한다. 모든 실제 시도는 호출 기록/예산에 남는다. 재시도가 실패해도 JSON 수정 요청으로 넘어가지 않는다.
- 진행 중 요청이 이미 서버에 전달됐거나 서버가 죽은 경우에는 터널 복구만으로 그 요청의 완료를 보장할 수 없다. 실패를 숨기거나 모델 답변을 만들어 계속하지 않는다.
- Slurm walltime이 만료되면 자동으로 새 GPU를 계속 할당하지 않는다. 새 실행을 막고 재시작을 안내한다. Ctrl+C로 반환 확인 후 `python3 -m uxagent dashboard`로 다시 시작한다. 자동 복구는 무한 GPU 갱신 기능이 아니다.
- 종료 시 로그인 master가 없어졌으면 다시 인증해 자기 작업만 반환한다. 반환을 확인하지 못하면 `runs/private/gpu-session-state.json`을 유지한다. 이 파일만 삭제하거나 사용자 전체 작업을 scancel하지 않는다. 같은 이름·ID의 소유권과 원격 종료를 확인한 뒤에만 복구 기록을 정리한다.
- 종료된 TCP 연결의 TIME_WAIT를 살아 있는 listener와 구분한다. 시작 포트 검사는 SO_REUSEADDR를 사용한다. 터널 복구는 OpenSSH의 실제 bind와 ExitOnForwardFailure에 맡기며 별도의 단순 bind 검사로 복구를 지연시키지 않는다.

수동 터널의 SSH/Slurm 소유자는 앱이 아니므로 자동 재연결하지 않는다. health와 실행 전 검사는 적용되며 사용자가 원래 SSH 명령으로 연결한다.

## 4. JSON 생성·파싱 규칙

1. 기준 스키마는 `src/uxagent/schemas.py`. U 인식·피드백·계획·행동, Slow 중요도·성찰·Wonder, 설문은 각 계약으로 확인한다. 과거 필드와 임의 새 필드를 섞지 않는다.
2. 프롬프트에 해당 단계의 응답 형태·타입과 간결한 예시를 명시한다. GPU 요청은 `response_format=json_object`를 사용하지만 올바른 응답을 보장한다고 간주하지 않는다.
3. 긴 페이지는 기존 DOM 규칙 기반 변환 → 모델용 짧은 행동 ID → 조각 인식 경로를 사용한다. 현재 큰 GPU 화면의 인식 조각은 1,400자다. 문자 수는 토큰 수의 정확한 측정이 아니므로 모델/토크나이저를 바꾸면 실제 서버 한도를 다시 확인한다.
4. 원본 observation JSON/PNG와 응답 근거를 보존한다. 모델 입력용 요약과 실제 원본을 혼동하지 않는다. 상품명·가격·옵션·입력·선택 대상·열린 메뉴의 상위 경로와 이웃 항목이 누락되지 않는지 회귀를 확인한다.
5. 기존 서버가 출력512토큰에서 중단한 사례가 있다. 조각 관찰은 합계240자 이하의 짧은 JSON을 지시한다. 출력 토큰 설정만 늘려 해결됐다고 판단하지 않는다. 큰 결합 결과는 기존 단계별 축약을 사용하며 정보 손실 가능성을 별도로 검증한다.
6. 로컬 교정은 GPU 인식 조각에서 이미 회귀로 확인한 후행 백틱·닫는 괄호 역순·마지막 배열 괄호 누락만 처리한다. 교정 후보가 JSON과 UPerception 검증을 모두 통과해야 한다. 본문 문자열의 따옴표·쉼표·값을 추측해 고치거나 빈 관찰/임의 행동을 생성하지 않는다.
7. Fast의 일반 JSON·스키마 오류는 모델 수정 요청을 한 번만 허용한다. 재요청에는 response model의 필수 구조로 만든 JSON 템플릿을 포함한다. 원본 JSON을 읽을 수 있으면 유효하게 제공된 선택/인자는 보존하고 빠진 필수 필드는 빈칸으로 보여 모델이 채우게 한다. JSON 문법 자체가 깨졌다면 해당 response model의 빈 구조를 제시하고 앞선 원본 응답을 같은 대화에 보존한다. 수정 시도·usage·예약 예산은 모두 기록한다. 연결 오류, HTTP/API 오류, TLS 오류를 JSON 수정 입력으로 보내지 않는다. Slow·설문에 같은 재시도 정책이 있다고 가정하지 말고 해당 구현을 확인한다.
8. `CancelledError`, BudgetExceeded, 실행 deadline은 즉시 원래 종료 흐름으로 보낸다. 취소된 요청의 usage가 없으면 미확인을 유지한다.
9. 여전히 잘못된 응답이면 해당 실행을 명확한 오류로 끝낸다. JSON 검사 통과는 내용의 진실성·올바른 행동·과업 성공을 증명하지 않는다.

### 실행 사실과 생성 해석의 불일치 방지

- SVG를 제거해도 이름이 있는 빈 아이콘 버튼을 버리지 않는다. dialog/aria-modal 경계를 flatten으로 지우지 않고 큰 GPU 입력에도 팝업과 그 안의 조작 대상을 보존한다. 자동으로 팝업을 닫거나 검색을 강제하지 않는다.
- 실제 실행된 첫 행동의 ActionResult를 다음 feedback·plan·decision에 전달한다. 미실행 제안이나 보이는 링크만으로 클릭 성공을 추정하지 않는다. 결과가 없으면 unknown이며, 실패 시 계획의 다음 표시를 무조건 넘기지 않는다.
- 열린 메뉴의 경로뿐 아니라 expanded/visible_children·모두 보기 링크를 관찰하고 계획에도 page_context를 전달한다. 동일 URL의 클릭 성공은 메뉴 확장일 수 있으며 사이트 고장이나 상품 목록 도달의 증거가 아니다. last_action과 결과를 함께 제공해 어떤 대상을 실제 시도했는지 알 수 있게 한다.
- 설문은 전체 기억과 별도로 실제 steps를 읽고 generated 기억을 사실과 구분한다. meta.execution_error_count가 실제 실패 수와 다르거나 누락되면 답변을 거부한다. 이 검사는 오류 수 일치만 확인하며 주관적 답변 전체의 정확성을 보장하지 않는다. 시행하지 않은 검색·필터를 실패했다고 표현하지 않는다.
- 설문 재실행이 실패하면 기존 survey.json은 survey.previous-<id>.json으로 보존하고 현재 답변에서 제외한다. 민감정보 검사는 새 실행 사실 입력에도 적용한다.
- GPU 인식용 입력은 동일 대상의 중복 control XML을 역할·이름·현재 값으로 간략화한다. 행동 선택용 ID/전체 관찰/메뉴·팝업 문맥은 유지한다. 변경 전후 동일 화면의 내용 보존과 실제 호출 수를 확인한다.
- GPU 채팅은 제공자 인스턴스 안에서 한 요청씩 전송한다. 대기 중 Fast가 Slow보다 우선하지만, Fast3건 연속 뒤에는 대기 Slow1건을 처리해 기억 갱신이 굶지 않게 한다. Fast/Slow 생성·Wonder·기억 정책을 끄지 않는다. 같은 실행의 두 루프는 같은 provider를 사용해야 이 대기열을 공유한다.
- 대기 중 취소된 요청은 서버로 보내지 않는다. 이미 보낸 요청은 호출자 취소만으로 원격 추론이 멈추지 않으므로 완료 전 다음 요청을 겹쳐 보내지 않는다. 취소 usage는 미확인을 유지하며 예산 요청 수는 논리 시도 수다. 성공한 Fast/Slow 호출에는 provider_queue_ms를 남겨 클라이언트 대기와 전체 elapsed를 구분한다. 여러 대시보드 프로세스 사이의 전역 스케줄러는 아니다.

## 5. 오류가 새로 나오면 진행할 순서

1. 같은 실패를 여러 페르소나로 반복 실행하지 않는다. 실행ID, 시각, stage, termination_reason, last_error, 최초 실패 호출을 확보한다.
2. 응답이 없는 전송 오류인지, HTTP 오류인지, 응답을 받은 JSON/스키마 오류인지 먼저 나눈다. 연결 오류면 health → 소유 Slurm 상태 → SSH 터널 순으로 확인한다.
3. JSON 오류면 **로컬에서만** 해당 `llm_calls.jsonl`의 request/response와 observation을 비교한다. 공개 이슈/보고서에는 비밀값·페이지 원문·개인정보를 복사하지 않는다. 기존 raw evidence 차단/마스킹을 유지한다.
4. 실패 입력/응답에서 최소 재현 테스트를 먼저 만든다. 토큰 초과, 비어 있는 배열, 여러 관찰, 본문 따옴표, 정상 JSON, 잘림, 접미부 교정 오인, 취소 중 동작을 구분한다.
5. 원인이 확인된 모듈만 고친다. 프롬프트 길이, 서버 출력 한도, 파서 계약, 연결 상태, GPU 경합을 한 원인으로 뭉뚱그리지 않는다.
6. 아래 회귀와 실제 연결 검사를 수행한다. 검사 결과는 mock/실제 HTTP/실제 생성/실제 브라우저 과업을 구분해서 기록한다.
7. 이 문서와 troubleshooting에 **증상 → 원인 → 해결 → 회귀 → 실제 검증 결과**를 추가한다. 미실행한 검사를 통과로 기록하지 않는다.

## 6. 변경 후 필수 검증

관련 검사:

```sh
python3 -m pytest -q tests/test_gpu_session.py tests/test_gpu_provider.py tests/test_gpu_ssh_keys.py tests/test_gpu_passwords.py tests/test_u_fast.py tests/test_u_slow.py tests/test_runner_flow.py tests/test_dashboard_browser.py
python3 -m compileall -q src/uxagent
node --check src/uxagent/dashboard/app.js
node --check src/uxagent/parser/parser.js
python3 scripts/check_repo.py
git diff --check
```

[개발 지침](development.md)에 따라 전체 `python3 -m pytest -q`, doctor와 mock 통합도 확인한다. 브라우저/로컬 포트 실행 권한 부족으로 실패하면 제품 버그와 구분하고 필요한 실행 권한에서 다시 검사한다. 실제 API 검사는 CI의 mock 검사와 다르며 자격증명·비용·범위를 확인한다.

대량 mock 통합 로그는 대시보드가 실행 기록을 재귀 조회하는 `runs/` 밖의 임시 경로에 둔다. 생성 호출 수가 많은 검증 로그를 운영 대시보드 폴링에 섞으면 상태 API가 느려질 수 있다. 요약 검증 결과만 문서에 남긴다.

회귀 기준:

- 정상 JSON과 기존 접미부 교정 통과, 내부가 깨진 JSON 거부, 여러 관찰 순서 보존, 입력/행동 ID 매핑 유지.
- 연결 거부 후 재시도 한도 준수, JSON 수정 요청 미전송, 실제 provider 오류 타입 보존.
- 채팅과 임베딩 health의 실제 모델 확인. 200이지만 다른 모델이면 거부.
- 연결 끊김 감지 → 연결됨 표시 해제 → 실패 시 실행 전 거부 → 복구 후 실행 가능.
- 소유 Slurm 할당이 RUNNING일 때만 터널 복구. 만료/타인 작업은 재사용·취소하지 않음.
- 로그인 master가 없어도 종료 시 자기 작업 반환. 반환 실패 시 상태 파일 유지.
- timeout/사용자 중지/예산 소진이 재시도와 복구보다 우선하고 로그·독립 판정이 유지됨.
- 실제 터널 중단 검사는 유휴 상태에서 자신의 SSH master만 종료해 수행한다. 복구 전후 작업ID가 같고, health와 짧은 생성 응답이 회복되는지 확인한다. 전체 사이트 성공은 별도다.

## 7. 검증 이력

- 2026-10-20: 새 회귀7건이 수정 전 실패하는 것을 확인했다. 수정 후 관련96건과 전체557건이 통과했다. 저장소 검사0 problems, diff 공백 검사 통과. 초기 브라우저 검사2건은 sandbox 권한 제한으로 실패했고 허용 환경에서 재검사했다.
- 같은 날 원격19375는 RUNNING인데 로컬 SSH master와 채팅/임베딩 listener가 모두 없었던 것을 확인했다. 소유권 검증 후 반환했다. 이후19376의 Slurm 종료 원인은 sacct의 TIMEOUT/04:00:08로 확인했다. 연결 장애와 할당 시간 만료를 구분한다.
- 실제 강제 중단 검사에서 첫 복구는 TIME_WAIT 사전 검사 때문에 재시도 한도를 넘겼다. 실제 TCP 재현 테스트를 추가하고 고친 뒤, 작업19378에서 login/compute SSH master를 모두 중단했다. 새 할당 없이 **6.92초**, 생성3회 시도, JSON 수정0회로 유효한 UPerception JSON을 얻었다. 복구 후 대시보드·Qwen·CUDA 임베딩 모두 HTTP200이었다. 전체 사이트 과업 성공을 검증한 것은 아니다.
- TIME_WAIT 수정 후 GPU·키·키체인 관련48건과 최종 전체 **558건**이 통과했다. doctor, mock 통합(독립 판정success), compileall, JavaScript 구문 검사, 저장소 검사0 problems, diff 공백 검사도 통과했다. 구체적 검증 범위는 [검증 기록](verification.md)을 따른다.

- 2026-10-20 실행 사실/메뉴/큐 후속: 전체580건 이후 단일 관찰 문자열 회귀를 추가하고 관련89건을 통과했다. 실제300초 과업은5행동 성공 후 판단 중 시간초과, 독립failure였다. 연결/JSON 정상과 과업 성공을 구분한다. 상세는 검증 기록을 따른다.
- 2026-10-21 action schema repair: 모델이 `description`을 생략한 UActions 응답으로 실행 전 중단된 사례를 확인했다. 다음 JSON 수정 요청은 response model에서 JSON 템플릿을 만들고, 원본의 유효한 action/target/text/enter는 보존하면서 누락한 `description`을 빈칸으로 보낸다. 문법이 깨져 원문을 읽을 수 없으면 비어 있는 필수 구조를 제시하고 원문은 직전 assistant 메시지로 보존한다. U Fast·prompt guard·target selection **46 passed in 4.64s**. 실제 Qwen 재요청 동작은 이번 검사에서 호출하지 않았다.

## 8. 관찰 문자열과 생성 길이 때문에 재호출되는 경우

1. 실제 호출 로그의 원본 response·output_tokens·provider_queue_ms를 확인한다. timeout에 따른 취소를 별도 모델 JSON 결함으로 세지 않는다.
2. GPU 조각 응답이 완전한 `{"observations":"문장"}`인 경우만 내용 그대로 한 원소 배열로 변환한다. 원본 응답 로그는 보존한다. 빈 문장·다른 타입·깨진 내부 JSON은 만들어 채우지 않는다.
3. feedback이 출력 한도에서 잘렸다면 문장 수와 반복 내용을 먼저 줄인다. 현재 지시는1~2개/각120자 이내다. 이는 생성 지시이며 스키마 검증을 대신하지 않는다. 모든 모델 응답을 무조건 문자열 복구하거나 성공 처리하지 않는다.
4. provider_queue_ms가 크면 단일 GPU에서 이미 실행 중인 Slow/다른 요청을 확인한다. Fast 우선 큐도 실행 중인 원격 추론을 선점하지 못한다. 기본 timeout을 늘려 지연을 숨기지 말고 별도 진단 실행의 시간 한도와 결과를 기록한다.
5. 관련 회귀 `tests/test_u_fast.py`, `tests/test_gpu_provider.py`와 실제 실패 입력의 짧은 재생을 확인한 뒤 전체 과업 실행 여부를 별도로 기록한다.

## 9. 상품 상세에서 독립 가격 판정만 미확인인 경우

1. final_evaluation.json의 reason과 name/price를 확인한다. 모델의 종료/설문 답변을 독립 성공으로 대신하지 않는다.
2. 등록 프로필의 detail_price 선택자가 실제 상품과 함께 구매 합계·추천 상품을 동시에 읽는지 실제 공개 DOM에서 확인한다. 상품 내 상충하는 중복 가격이면 미확인을 유지한다.
3. 실제 확인한 상품 정보 컨테이너로 선택자 범위를 좁힌다. 현재 공개 데카트론은 #product-summary-container를 사용한다. 사이트 변경 시 실제 DOM을 다시 확인한다.
4. 합계 제외와 상품 내부 충돌·가격 부재 회귀를 함께 확인한다. 기존 실행 기록은 덮어쓰지 않고 별도 재검사 결과와 원본 run ID를 남긴다.
5. 2026-10-20: 전체581건 후 프로필 수정 관련40건 통과. 별도600초 진단은7/7행동·394.70초·agent_finished·설문completed였다. 원래 독립unknown을 보존한 상태에서 동일 실제 페이지의 수정 프로필 재검사는 상품명/79,900원success였다. 기본300초 내 성공은 검증하지 못했다.

## 10. 정상 생성 중 과업 제한에 도달하는 경우

- 최신 사용자 요청으로 AI 전체 시간 제한은 기본 해제한다. 기본/데카트론/공개 데카트론 study의 run_timeout_seconds=null이며 대시보드600초 예외는 제거했다. 별도 study에 양수를 지정하면 그 제한을 적용한다.
- 사용자 지정 study의 명시 제한은 자동으로 바꾸지 않는다. 기존123초 보존 검사는 과거 기록이며 이번 null 기본값 변경은 사용자 요청으로 테스트하지 않았다.
- 전체 시간 제한 해제는 성공 보장이나 처리 속도 향상이 아니다. 실제elapsed·종료 이유·독립 평가·설문 결과를 각각 확인한다. 시간초과 기록을 지우거나 오류 통계에서 성공으로 바꾸지 않는다.

## 11. 모든 Qwen 요청의 전송 전 검사와 반복 요약

1. Fast/Slow/Wonder/설문의 준비 경로와 provider.complete가 공통 PromptGuard를 사용한다. 먼저 전체 메시지의 system/role/컨텍스트와 출력 예약을 포함해 크기를 확인한다. JSON 수정 차례도 다시 검사한다.
2. 입력8192토큰은 현재 실제 원격 코드에서 확인한 상한이다. 클라이언트는 정확 tokenizer가 없으므로 보수적 추정+1024토큰 여유+최대512출력 예약을 사용한다. 로그의 prompt_guard.exact_token_count=false를 유지한다. 서버/모델 한도가 바뀌면 PromptGuard 한도와 추정을 함께 재검토한다.
3. 초과하면 긴 기억·관찰·이전 계획을3500바이트 이하 조각으로 모두 읽어 중요 내용 요약→병합→전체 재검사를 한다. 병합본이 크면 요약을 다시 나눠 반복한다. 잘라서 일부 원문만 전송하지 않는다. 요약에는 이름/가격/조건/실패/불확실성/제안과 사실의 구분을 유지하도록 지시하지만 의미 손실을 완전히 보장하지는 못한다.
4. system·페르소나/과업 조건·질문지·실제 실행 trace·현재 행동 대상 ID와 메뉴/팝업/컨트롤 대응은 요약하지 않는다. 보호 정보 자체가 크면 prompt_preflight_error로 중단하며 임의로 계약을 축약하지 않는다. 이 경우 어떤 보호 입력이 커졌는지 개발자가 확인해야 한다.
5. llm_calls.jsonl에서 stage=prompt_summary와 parent_stage/round/chunk_index/chunk_count를 확인한다. 추가 호출은 기존 공통 예산에 포함된다. 요약 실패/비수렴/취소·예산 소진이면 성공 응답을 만들지 않는다. 원본 trace와 요약된 실제 요청은 별도로 남는다.
6. summary JSON이 잘렸거나 비어 있으면 입력 크기 오류와 구분한다. 실제 summary response와 출력 사용량을 확인하고 단순 JSON 수정으로 원본 전체를 다시 보내지 않는다. 요약 호출 수가 많아지면 지연이 늘 수 있으며 기본 전체 실행 시간 제한 해제와는 별개다.
7. 회귀는 tests/test_prompt_guard.py 및 Fast/Slow/설문/호출 근거 검사를 사용한다. 저장된 실패 요청의 가짜 요약 재생과 실제 GPU 추론 검증은 구분해서 기록한다. 이전 오류 run과 설문은 덮어쓰지 않는다.

## 12. 보호 입력 때문에 막히는 경우: 정확 계수와 단계적 대상 선택

이 절이11절의 최초 문자 추정보다 우선한다.

- 실제 사례20261021T031048-4faff60e는 보호 컨트롤이 넘친다고 거부됐다. 지침/중복을 줄인 뒤 같은 관찰 화면으로 재구성한 행동 입력은 문자 추정6993에 비해 실제2863토큰이었고 사전 계수와 Qwen 응답 usage가 일치했다.6993은 수정 후 입력에 종전 추정식을 적용한 값이며 당시 실패한 원문 요청의 정확 토큰 수가 아니다. 행동 제안은2.44초에 완료했으며 전체 과업 시간 측정이나 실제 클릭 성공은 아니다.
- 기본 관리 GPU는 CPU 토큰 계산 서비스를 함께 켠다. 별도 키/모델 설치 없이 기존 chat venv·모델의 토크나이저를 쓴다. 새 로컬/원격 포트는 기본8003이며 기존 채팅/임베딩과 달라야 한다. 서비스도 Slurm 작업과 함께 종료된다. 수동 연결은 동일 서비스를 띄우고 PERSONA_QWEN_TOKENIZER_URL=http://127.0.0.1:<local_port>/tokenize를 설정해야 정확 계수를 사용한다. URL이 없으면 추정임을 표시한다.
- llm_calls의 prompt_guard.exact_token_count/input_tokens/tokenizer_fingerprint를 확인한다. exact_token_count=true의 input_tokens를 서버 input_tokens와 비교한다. 예상과 다르면 모델 파일·transformers 환경·채팅 템플릿 옵션·입력8192 상한이 같은지 확인한다. 설정된 계산 서비스가 꺼졌다고 추정값으로 계속하지 않는다.
- 긴 고정 지침은 작은 계약으로 유지하고, 중복 컨트롤은 코드로 합친다. 조작 대상 자체가 많으면 target_selection에서 먼저 구역을 선택한다. 메뉴 경로와 팝업/상단/상품 구역을 구분하며 선택 후 실제 세부 ID/이름/값을 전달한다. 이 선택이 브라우저 행동을 실행한 것은 아니다. 관련 없는 구역을 골랐는지는 인지 품질 문제로 별도 확인한다.
- prompt_summary의 JSON이 실패하면 해당 조각에 repair_attempt=1이 있는지 확인한다. 원본 전체나 보호 지침을 다시 요약하지 않는다. 선택/요약 반복에는 상한이 있고 예산·취소가 우선한다.
- model_input_error의 section_bytes와 input_tokens를 보면 어느 보호 정보가 큰지 알 수 있다. 한 개의 컨트롤 또는 고정 과업 자체가 한도를 넘으면 임의로 조건을 버리지 않고 중단한다. 모델 문맥 한도와 데이터 표현을 함께 검토한다. 진단에는 원문 대신 크기를 기록한다.
- tokenizer 서비스가 켜지지 않으면 .persona-gpu의 해당 소유 작업 로그와 api_server.py의 MODEL_PATH/MODEL_NAME 문자열 상수, 같은 chat venv의 transformers를 확인한다. API 서버 파일은 자동으로 수정하지 않는다. Slurm 반환 확인 없이 상태 파일만 지우거나 타인 작업을 취소하지 않는다.
