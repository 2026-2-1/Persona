# Persona / UXAgent Prototype

가정 페르소나 AI가 웹 과업을 수행하고, 독립 판정과 실행 근거를 바탕으로 개발자가 검토할 개선 후보를 보여주는 로컬 연구 도구입니다.

개발 통합 기준은 `prototype`입니다. 2026-10-19 [PR #101](https://github.com/2026-2-1/Persona/pull/101)의 일반 merge 커밋 `9095b3c`에 #95~#99와 기존 D 보완, 코드 검토 5건 수정이 함께 포함됐습니다. 해당 6개 PR은 모두 병합 처리됐고 원격 브랜치 정리도 완료했습니다. #100은 #101로 대체해 종료했습니다.

[병합 후 CI](https://github.com/2026-2-1/Persona/actions/runs/39208715049)는 Ubuntu/Python 3.11 **574 passed**, Windows/Python 3.13 **569 passed, 5 skipped**이며 두 환경의 doctor·무료 Mock 실행도 통과했습니다. Windows 제외 5건은 POSIX SSH/agent 검사입니다. [현재 상태](docs/current-state.md), [최종 prototype 검증·팀원 재현 절차](docs/handoffs/2026-10-19-prototype-verification.md), [검증 기록](docs/verification.md)을 기준으로 확인하세요. 이 결과는 실제 GPU Qwen의 과업 성공이나 사람 판단 일치도 검증과 구분합니다.

현재 Fast Loop는 최초 인식 → 계획 → 행동, 이후 feedback·인식 동시 실행 → 계획 → 행동입니다. 첫 인식 뒤 단일 Slow Loop가 reflect → wonder → memory.update를 반복하고 공유 기억에 직접 저장합니다. 활성 기억은 최대 64개이며, 새 실행에는 예전 plan_review·채택 게이트·1% Wonder 추첨을 적용하지 않습니다. 구형 기록은 계속 조회합니다. [Fast](docs/tasks/83-u-fast.md) · [Slow](docs/tasks/84-u-slow.md) · [기억 검색](docs/tasks/85-u-memory.md)을 참고하세요.

U DOM parser·semantic ID 행동, 질문지와 전체 누적 기억 기반 사후 설문, 종료 후 독립 평가, 기존 검토 저장·이력·네 형식 출력이 연결됐습니다. 비밀번호 관찰값과 Slow 민감 출력, 큰 GPU 화면의 조작 정보, 실제 취소 기록, 설문 실패 재시도 수정도 포함합니다. [U 통합 계약](docs/tasks/90-u-transition-08.md), [수정 이력](docs/handoffs/2026-10-19-review-fixes.md)에 범위를 정리했습니다.

GPU 자동 시작·반환과 macOS 키체인/SSH 키 최초 설정은 [GPU 수명주기 안내](docs/tasks/gpu-dashboard-lifecycle.md)를 따릅니다. 실제 Qwen health·임베딩 벡터·자원 반환의 과거 확인과 이번 통합 코드의 생성·과업 검증을 구분합니다.

## 빠른 시작 (Windows)

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m uxagent doctor --study configs/study.json
.venv/Scripts/python.exe -m uxagent dashboard
```

[로컬 대시보드](http://127.0.0.1:8765)에서 **무료 데모로 시작 → 다음 → 다음 → 다음 → 테스트 실행**으로 진행합니다. 목표·사용자·모델·실행 확인의 4단계이며 마지막 버튼에서 사용자 생성과 실행이 자동으로 이어집니다. 마지막 단계에서 **AI 비교**를 선택하면 일반 AI와 페르소나 AI를 같은 조건으로 비교합니다. 별도의 페르소나 생성 버튼을 찾을 필요가 없습니다.

API 연결 없이 검색·필터·상세와 개선 후보를 점검하려면 **API 없는 과업 점검 → 다음 → 시나리오 선택 → 다음 → 다음 → 점검 실행**을 선택하세요. 준비된 합성 페이지의 네 가지 과업과 재현 결함을 실행합니다. **공개 데카트론 부분 점검 (실험)**은 지정된 검색 URL부터 가격 상한·상세 이름/가격을 확인합니다. [시나리오 사용법과 판정 범위](docs/offline-scenarios.md)를 참고하세요.

macOS/Linux 설치와 개발 검사는 [개발 안내](docs/development.md)를 참고하세요. Python 3.11+가 필요합니다.

## 현재 MVP

- **과업 테스트:** 검색·가격/색상 필터·상세 확인을 로컬 fixture의 독립 평가기로 판정합니다.
- **API 없는 점검:** 검색→필터→상세, 빈 결과와 검색어 변경, 필터 초기화, 스크롤 안내의 사전 정의된 단계를 실행하고 단계별 코드 판정·PNG·URL·미검토 카드를 기록합니다. AI/페르소나 비교 결과와 구분합니다.
- **외부 사이트:** visible / text_contains / url_contains 확인 조건을 등록할 수 있습니다. 조건이 없으면 성공 미확인입니다.
- **합성 데카트론 AI 실행:** `configs/study-decathlon.json`에서 과업과 평가 기대값을 분리합니다. `python3 -m uxagent run --study configs/study-decathlon.json --provider live --headless`로 실행할 수 있으며 OpenAI API 키와 사용 요금이 필요합니다. 상세 상품명·색상·가격 조건이 모두 맞아야 독립 평가가 성공합니다.
- **공개 데카트론 AI 부분 실행:** `configs/study-decathlon-live.json`은 공개 검색 결과에서 러닝화 상세의 표시 이름·가격만 확인합니다. `python3 -m uxagent run --study configs/study-decathlon-live.json --provider live --headless`는 OpenAI API 키가 필요하며, 검색 폼 제출·색상·사이즈·재고·픽업 성공을 판정하지 않습니다.
- **AI 비교:** 같은 구매 제약·모델·환경에서 인물 배경·탐색 성향만 제외한 일반 AI와 페르소나 AI를 비교합니다. 두 조건 모두 실행별 Brain/Fast/Slow를 사용하고, 일반 조건 Slow에는 개인 배경·선호를 전달하지 않습니다. 예정 세션·중지·오류도 분모에 남깁니다.
- **실행 기록:** 검색(사용자·모델·ID)과 결과 필터로 12건 이후 기록까지 접근할 수 있습니다. 전후 화면·URL·행동·판정·모델 호출과 기록 확보율을 봅니다. 복구는 '오류 후 3행동 내 도구 실행 성공'이라는 보조 지표이며 과업 성공과 구분합니다.
- **Brain·Slow 근거:** 하나의 기록 패널에서 생성 단계·작업 상태·기억 점수와 제거 원본·Wonder 생각의 저장 여부·선택 행동의 독립 결과를 확인합니다. 새 U 실행의 매 반복 Wonder와 구형 1% 추첨/채택·폐기 기록을 구분합니다. 생성·저장 기록만으로 행동 실행이나 과업 성공을 단정하지 않습니다.
- **개선 보드:** 원시 근거는 접고, 분류·수정 제안·근거 버튼을 먼저 보여줍니다. 관찰·원인 가설·제안·완료 조건·근거를 구분한 미검토 후보를 제공합니다. JSON·CSV·Markdown·HTML로 내보냅니다.
- **디자인:** 사용자 제공 [디자인 기준](docs/design.md)의 단색 UI에 Pretendard(-3% 자간)와 이미지 생성으로 만든 테두리 없는 P 심볼과 ersona 글자를 좁은 간격으로 조합한 Persona 로고를 적용했습니다. 폰트는 로컬 제공하며 반복 설명과 상단 상태 바를 줄이고, 왼쪽 사이드바를 로고 옆 왼쪽 정렬의 상단 메뉴로 옮기고 설정·최근 테스트 카드 너비를 맞췄습니다. 본문의 중복 제목은 숨기고 설정/최근 기록과 실행 근거/판정을 좌우로 배치합니다. 추가 기록·프로필·내보내기는 접어서 읽으며 모바일은 한 열을 유지합니다. 기능 판정은 아이콘·항목·상태가 정렬된 체크리스트이며 행을 눌러 근거를 확인합니다.

## API 연결

GPU 서버의 `persona-qwen` 모델을 사용하려면 먼저 원격 `api_server.py`와 SSH 터널을 실행하고 `curl http://127.0.0.1:8000/health`로 확인합니다. 대시보드 3단계에서 **GPU 서버 — Qwen3.5-9B → 연결 확인**을 선택하면 키 없이 실제 채팅 요청으로 확인합니다. CLI는 `--provider gpu`를 사용합니다. 기본 채팅 주소는 `http://127.0.0.1:8000/v1/chat/completions`이며, 다른 로컬 포트로 터널을 열었다면 `PERSONA_QWEN_API_URL`에 전체 채팅 주소를 설정합니다. GPU 할당과 터널은 사용 중 유지해야 합니다. [실행 순서](docs/development.md#gpu-서버-qwen-연결)를 참고하세요.

기본 합성 사이트도 로컬 8000번 포트를 사용합니다. 합성 사이트에서 GPU 모델을 시험할 때는 터널의 로컬 포트를 8001 등 다른 번호로 열고 `PERSONA_QWEN_API_URL`을 그 포트로 맞춥니다. 공개 사이트 설정인 `configs/study-decathlon-live.json`은 이 충돌이 없습니다. GPU 모델의 실제 비용은 서버 응답만으로 알 수 없으므로 비용 미확인으로 기록합니다.

Qwen 서버는 공개 데카트론의 큰 첫 화면 HTML을 그대로 받으면 `Prompt too long`으로 거절합니다. 큰 화면의 인식은 원본 HTML에서 내부 parser 속성만 제외하고 모든 조각을 나눠 읽은 뒤, 각 관찰을 다시 합치는 과정을 한 결과가 남을 때까지 반복합니다. 원본 관찰과 실행용 semantic ID는 보존하며 조각별 요청·응답은 비공개 실행 로그에 남깁니다. 반복 요약은 모든 문구 보존을 보장하지 않으며, 이 Qwen 호환 경로는 논문 UXAgent의 전체 HTML 설명과 다릅니다. 과업 성공은 별도 평가로 확인해야 합니다.

대시보드 3단계에서 GPU 서버 / OpenAI / Claude / Gemini / Jev+Gemini를 선택하고 **연결 확인**을 누릅니다. GPU 서버는 SSH 터널을 사용하며 키 입력이 필요 없습니다. 다른 제공자는 API 키가 필요하고 Jev는 Gemini 연결도 필요합니다. 연결 확인은 작은 실제 요청을 보냅니다. 키는 서버 프로세스 메모리에만 보관하고 브라우저 저장소·원자료·저장소에 쓰지 않습니다. 서버 재시작 시 다시 연결해야 합니다. 로컬 `.env`로 설정해도 되며 프로세스의 기존 값을 덮어쓰지 않습니다. `.env.example`에는 빈 변수만 있습니다.

Mock은 번들 shop.html 전용입니다. Jev는 선택 후보를 분류하고 입력 문구가 필요하면 Gemini가 생성합니다. 낮은 신뢰도·잘못된 선택·Jev 오류에도 Gemini fallback을 사용합니다. OpenAI 경로는 기존 Chat Completions API, Claude는 Anthropic Messages API와 Claude Sonnet 4.6을 사용합니다. Claude 키 변수는 `ANTHROPIC_API_KEY`입니다. 연결되지 않은 유료 모델은 다음 단계로 진행할 수 없습니다.

**ChatGPT 구독 로그인은 아직 구현하지 않았습니다.** 적격 로컬/오픈소스 앱의 공식 구독 연동 PoC는 후속 이슈로 관리합니다. 공개 호스팅·다중 사용자 키 관리도 이 MVP 범위 밖입니다.


## 모델 선택과 설정 도우미

3단계에서 제공자와 모델을 선택하고 **키 발급 페이지 → 키 입력 → 연결 확인**으로 진행합니다. 모델을 바꾸면 다시 연결을 확인합니다. 오른쪽 도우미의 쇼핑 검색·정보 찾기·예약 안내·입력 오류는 시작용 예시이며 사용 빈도 순위가 아닙니다.

연결 전에는 무료 예시와 공식 발급 안내를 제공합니다. 연결 확인 후 **추천받기** 또는 질문 전송을 누르면 선택한 모델을 호출합니다. 추천 사용자·목표는 적용 버튼을 눌러야 설정에 반영됩니다. 추천은 가정이며 실제 사용자 조사 결과가 아닙니다. 최종 사용자 프로필 생성은 기존 로컬 템플릿을 유지합니다.

도우미는 서버 실행당 최대 5회, 보수적 토큰 예산 12,000, 출력 최대 1,000/회입니다. 실패 요청도 한도를 소비합니다. 사용량과 비용은 응답에 나온 값이며 계정 잔액과 다릅니다. 가격을 확인할 수 없는 모델은 비용 미확인으로 표시합니다. 대화는 메모리에만 유지하며 키·인증 URL은 질문에 입력하지 않습니다.

지원 모델 목록은 현재 구현과 호환되는 선택지이며 최신·전체 모델 목록을 보장하지 않습니다. Gemini 2.5 접근이 제한된 계정은 3.5 Flash Lite를 확인하세요. Jev 키 메뉴의 상세 경로는 확인되지 않아 콘솔 안내를 따릅니다. 실제 유료 API 연결은 개발 검증에 포함하지 않았습니다.

## C 담당 데이터·검토 기능

카드에는 기존 ID와 내용 버전이 포함되며, 사람 판정을 실행 하위 JSONL 이력으로 저장합니다. `GET /api/reviews/<run_id>`로 조회하고 같은 경로에 카드 ID/버전·검토자 별칭·판정·메모를 POST하면 저장합니다. [C 작업 사용법과 API 계약](docs/tasks/c-review-data.md), [가상 응답 예시](docs/examples/c-review-contract.json)를 참고하세요.

검토는 유효·무효·보류·도구 오류·환경 오류로 나눕니다. 개선 보드에서 별칭·판정·메모를 저장하고 현재/이전 버전 이력을 확인합니다. 이전 판정은 보존하고 현재 버전의 최신 판정만 카드와 출력에 반영합니다. 자동 갱신·실행 왕복 중 미저장 초안을 유지하며, 저장한 판정은 새로고침 후에도 남습니다. 과업 성공 판정은 바꾸지 않습니다. 검토자 별칭은 로그인 인증이나 2인 합의를 뜻하지 않습니다.

비교 집계는 오류·취소·미실행을 포함한 예정 분모를 유지합니다. scripted 점검은 AI 비교에서 제외하고, 비용·토큰·기록이 일부만 있으면 전체값과 알려진 부분값·누락 수를 구분합니다. 기존 저장 실험은 파일을 수정하지 않고 조회 시 집계합니다. 새 실행은 실제 사용량과 예산 예약값을 구분하며, 사용량을 받지 못하면 0으로 표시하지 않습니다.

## 명령과 검증

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check_repo.py
.venv/Scripts/python.exe -m uxagent run --study configs/study.json --provider mock --headless
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect filter
.venv/Scripts/python.exe -m uxagent personas --config configs/personas.json --output runs/personas
.venv/Scripts/python.exe -m uxagent compare --study configs/study.json --personas runs/personas/personas.jsonl --provider mock --repetitions 1
```

관찰·실행 원자료는 Git에서 제외된 `runs/` 아래에 저장합니다. 비교 실험은 `runs/experiments/<id>/experiment.json`과 대응 실행 기록을 생성합니다. 설문은 질문지(`configs/survey.json`)와 전체 누적 기억 trace로 실행 후 GPU Qwen 응답을 만들며 batch에서는 모든 브라우저 세션 뒤에 수행합니다. `python3 -m uxagent survey --run runs/<run-id> --provider gpu`로 단독 실행할 수 있습니다. 결과는 `simulated_self_report`이고 실제 사람 증언이나 독립 성공 판정이 아닙니다. `review`와 `interview` 경로는 별개로 유지합니다.

[검증 기록](docs/verification.md)에서 실제 확인 범위를 확인하세요. CI는 Windows/Python 3.13과 Ubuntu/Python 3.11의 mock·테스트만 실행하며 라이브 API 키를 사용하지 않습니다.

## 개발 진입점

- 연구·회의 자료: [실험 계획](docs/research/2026-10-15-slow-loop-experiment-plan.md), [회의 안건](docs/meetings/2026-10-15-research-and-data-agenda.md), [기업 데이터·시스템·Novelty 제출 초안](docs/research/2026-10-15-project-submission-draft.md). 기업 데이터는 사용자 확인 기준 미수령 0건이며 조건·목표 수량은 제안입니다.
- 협업: [브랜치·커밋](docs/collaboration.md), [PR·리뷰](docs/pull-requests.md)
- 운영: [브랜치 보호](docs/branch-protection.md), [디스코드 알림 연결 준비](docs/discord-notifications.md)

- AI 작업 규칙: [AGENTS.md](AGENTS.md)
- 문서 목차: [docs/README.md](docs/README.md)
- 현재 구현과 제한: [현재 상태](docs/current-state.md)
- Brain·두 루프: [현재 Fast](docs/tasks/83-u-fast.md), [현재 Slow](docs/tasks/84-u-slow.md). [초기 설계](docs/plans/2026-10-14-brain-two-loops.md)의 plan_review·채택 게이트는 과거 설계입니다.
- 다음 개발 순서: [로드맵](docs/roadmap.md), [이슈·작업 목록](docs/tasks/README.md)
- 입출력·판정 기준: [계약](docs/contracts.md)
- 변경 시 함께 확인할 문제: [트러블슈팅](docs/troubleshooting.md)
- 장기 제품 제안: [통합 기획 초안](docs/2026-10-09-persona-product-plan.md)

기능 브랜치에서 `prototype` 대상 PR로 작업합니다. GitHub 이슈 템플릿은 기본 브랜치에 반영된 뒤 생성 UI에 나타납니다. 이번 설정은 `prototype`에 적용하며 `main` 통합은 별도로 진행합니다.

## 해석과 제한

모의 행동·응답은 실제 사용자 증언이나 인간 행동 재현의 증거가 아닙니다. 문제 후보는 사람 검토 전이며, 후보가 없다고 사이트에 문제가 없다는 뜻도 아닙니다. 비교의 mock 결과는 시스템 흐름 검증용이고 페르소나 효과 측정 결과가 아닙니다.

viewport DOM 관찰이며 iframe·canvas·복잡한 shadow DOM은 완전히 처리하지 않습니다. U action 실행 전 AI 경로의 allowed-origin·최신 observation/registry·capability 제한은 제거됐습니다. 모델이 제안한 URL 이동도 브라우저에서 시도하며 Playwright 실패는 도구 오류로 남깁니다. `allowed_origins`는 이전 study 파일의 호환 입력이고 scripted offline scenario는 별도 origin/read-only 경계를 유지합니다. 예산·timeout·사용자 stop, GPU API URL·local server bind·파일 경로·인증정보 보호는 유지합니다. custom combobox의 범용 지원을 보장하지 않으며 실제 Qwen 생성/데카트론 과업 성공은 별도 검증 대상입니다.

2026-10-11 공개 데카트론의 사전 지정 검색 결과 → 8만원 상한 → 킵코어 상세 79,900원 부분 점검을 실제 Python 실행기에서 확인했습니다. 홈페이지 한글 검색 폼 제출은 별도 시도에서 미확인이었습니다. 색상·사이즈·재고·픽업·전체 상품 목록은 성공 범위에 포함하지 않습니다. 상세 결과는 [검증 기록](docs/verification.md)에 남깁니다.

#46에서 Fast·Slow·Wonder의 호출별 실제 제공자·모델·사용량·미확인 비용과 요청/토큰 한도 사유를 기록합니다. Jev는 행동 후보 선택에 쓰고 생성 단계에는 선택한 Gemini 모델을 사용합니다. Jev와 Gemini 키가 모두 필요하며 미지원 embedding 조합은 실행 전에 거부합니다. 기본 요청/총토큰 상한은 무제한으로 유지하며, 일반 AI 비교 조건에는 persona 배경·선호를 보내지 않습니다. [계약과 제한](docs/tasks/46-loop-provider-budget.md)을 확인하세요.

`.env`, API 키, OAuth 토큰, 인증 상태, 원본 개인 문서와 고객 개인정보는 push하지 않습니다.

D-01: 개선 보드의 사람 판정 입력·저장과 오류 처리는 prototype에 통합됐습니다. [검토 화면 안내](docs/tasks/d-review-form.md)를 따릅니다.

D-02: 자동 갱신·실행 전환 시 검토 초안과 텍스트 선택을 보존하며, 지연 조회가 최신 판정을 덮어쓰지 않도록 보완했습니다. 범위와 병합 순서는 [검토 화면 안내](docs/tasks/d-review-form.md)를 참고하세요.

D-03은 개선 보드의 현재/이전 버전 사람 검토 이력과 실행 방식·대상 출처를 제공합니다. Brain 기록 시각화(#47)도 prototype에 통합됐습니다. [사용법](docs/tasks/d-review-form.md), [검증 결과](docs/verification.md)를 확인하세요.

D-04는 비교표에 예정 분모·실행 상태·중앙값 계산 대상과 비용/토큰/기록의 측정 범위·누락을 표시합니다. [표시 계약과 검증](docs/tasks/d-comparison-coverage.md)을 참고하세요.

팀 공유: [D 진행 현황과 프로토타입 회의 안건](docs/meetings/2026-10-14-d-progress-and-decisions.md)에서 구현/통합 상태, D-05, 추가 수정 후보와 결정할 사항을 확인할 수 있습니다.

D-05는 병합된 prototype에서 후보 근거 확인·판정 저장·새로고침·네 형식 내보내기를 재검증했습니다. 팀원의 독립 재현은 #36의 남은 조건입니다. [재현 절차와 남은 팀 검증](docs/tasks/d-review-export-verification.md)을 참고하세요.

D 후속: [조회 실패·출처·복구 표시](docs/tasks/d-dashboard-hardening.md)를 보완했습니다. 메모리 정책 연구는 [실험 설계](docs/research/2026-10-15-memory-policy-experiment.md)를 참고하세요.

[D Brain 기록 연결](docs/tasks/d-brain-trace-viewer.md): 단계별 AI 생성 결과·비동기 마지막 상태·제거된 기억 원본을 화면과 네 형식 보고서에서 확인합니다.

2026-10-15 [아침 공유·재현·리뷰 순서](docs/handoffs/2026-10-15-morning.md)에 D 보완과 A+D 격리 통합의 실제 결과 및 남은 범위를 정리했습니다.
