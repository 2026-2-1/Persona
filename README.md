# Persona / UXAgent Prototype

가정 페르소나 AI가 웹 과업을 수행하고, 독립 판정과 실행 근거를 바탕으로 개발자가 검토할 개선 후보를 보여주는 로컬 연구 도구입니다.

## 빠른 시작 (Windows)

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m uxagent doctor --study configs/study.json
.venv/Scripts/python.exe -m uxagent dashboard
```

[로컬 대시보드](http://127.0.0.1:8765)에서 **무료 데모로 시작 → 다음 → 다음 → 다음 → 테스트 실행**으로 진행합니다. 목표·사용자·모델·실행 확인의 4단계이며 마지막 버튼에서 사용자 생성과 실행이 자동으로 이어집니다. 마지막 단계에서 **AI 비교**를 선택하면 일반 AI와 페르소나 AI를 같은 조건으로 비교합니다. 별도의 페르소나 생성 버튼을 찾을 필요가 없습니다.

macOS/Linux 설치와 개발 검사는 [개발 안내](docs/development.md)를 참고하세요. Python 3.11+가 필요합니다.

## 현재 MVP

- **과업 테스트:** 검색·가격/색상 필터·상세 확인을 로컬 fixture의 독립 평가기로 판정합니다.
- **외부 사이트:** visible / text_contains / url_contains 확인 조건을 등록할 수 있습니다. 조건이 없으면 성공 미확인입니다.
- **AI 비교:** 같은 구매 제약·모델·환경·호출 상한에서 인물 배경·탐색 성향만 제외한 일반 AI와 페르소나 AI를 비교합니다. 예정 세션·중지·오류도 분모에 남깁니다.
- **실행 기록:** 검색(사용자·모델·ID)과 결과 필터로 12건 이후 기록까지 접근할 수 있습니다. 전후 화면·URL·행동·판정·모델 호출과 기록 확보율을 봅니다. 복구는 '오류 후 3행동 내 도구 실행 성공'이라는 보조 지표이며 과업 성공과 구분합니다.
- **개선 보드:** 원시 근거는 접고, 분류·수정 제안·근거 버튼을 먼저 보여줍니다. 관찰·원인 가설·제안·완료 조건·근거를 구분한 미검토 후보를 제공합니다. JSON·CSV·Markdown·HTML로 내보냅니다.
- **디자인:** 사용자 제공 [디자인 기준](docs/design.md)의 단색 UI에 Pretendard(-3% 자간)와 이미지 생성으로 만든 테두리 없는 P 심볼과 ersona 글자를 좁은 간격으로 조합한 Persona 로고를 적용했습니다. 폰트는 로컬 제공하며 반복 설명을 줄이고 대시보드 요약을 가운데 정렬·큰 글자로 표시합니다.

## API 연결

대시보드에서 3단계에서 OpenAI / Claude / Gemini / Jev+Gemini를 선택해 키를 입력하고 **연결 확인**을 누릅니다. Jev는 Gemini 연결도 필요하며 필요한 키 입력만 표시합니다. 작은 실제 요청으로 연결을 확인하므로 API 사용 요금이 발생할 수 있습니다. 키는 서버 프로세스 메모리에만 보관하고 브라우저 저장소·원자료·저장소에 쓰지 않습니다. 서버 재시작 시 다시 연결해야 합니다. 로컬 `.env`로 설정해도 되며 프로세스의 기존 값을 덮어쓰지 않습니다. `.env.example`에는 빈 변수만 있습니다.

Mock은 번들 shop.html 전용입니다. Jev는 선택 후보를 분류하고 입력 문구가 필요하면 Gemini가 생성합니다. 낮은 신뢰도·잘못된 선택·Jev 오류에도 Gemini fallback을 사용합니다. OpenAI 경로는 기존 Chat Completions API, Claude는 Anthropic Messages API와 Claude Sonnet 4.6을 사용합니다. Claude 키 변수는 `ANTHROPIC_API_KEY`입니다. 연결되지 않은 유료 모델은 다음 단계로 진행할 수 없습니다.

**ChatGPT 구독 로그인은 아직 구현하지 않았습니다.** 적격 로컬/오픈소스 앱의 공식 구독 연동 PoC는 후속 이슈로 관리합니다. 공개 호스팅·다중 사용자 키 관리도 이 MVP 범위 밖입니다.

## 명령과 검증

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check_repo.py
.venv/Scripts/python.exe -m uxagent run --study configs/study.json --provider mock --headless
.venv/Scripts/python.exe -m uxagent personas --config configs/personas.json --output runs/personas
.venv/Scripts/python.exe -m uxagent compare --study configs/study.json --personas runs/personas/personas.jsonl --provider mock --repetitions 1
```

관찰·실행 원자료는 Git에서 제외된 `runs/` 아래에 저장합니다. 비교 실험은 `runs/experiments/<id>/experiment.json`과 대응 실행 기록을 생성합니다. `review`, `survey`, `interview` CLI도 유지하며 기존 설문·인터뷰는 기록 기반 템플릿입니다.

[검증 기록](docs/verification.md)에서 실제 확인 범위를 확인하세요. CI는 Windows/Python 3.13과 Ubuntu/Python 3.11의 mock·테스트만 실행하며 라이브 API 키를 사용하지 않습니다.

## 개발 진입점

- AI 작업 규칙: [AGENTS.md](AGENTS.md)
- 문서 목차: [docs/README.md](docs/README.md)
- 현재 구현과 제한: [현재 상태](docs/current-state.md)
- 다음 개발 순서: [로드맵](docs/roadmap.md), [이슈·작업 목록](docs/tasks/README.md)
- 입출력·판정 기준: [계약](docs/contracts.md)
- 변경 시 함께 확인할 문제: [트러블슈팅](docs/troubleshooting.md)
- 장기 제품 제안: [통합 기획 초안](docs/2026-10-09-persona-product-plan.md)

기능 브랜치에서 `prototype` 대상 PR로 작업합니다. GitHub 이슈 템플릿은 기본 브랜치에 반영된 뒤 생성 UI에 나타납니다. 이번 설정은 `prototype`에 적용하며 `main` 통합은 별도로 진행합니다.

## 해석과 제한

모의 행동·응답은 실제 사용자 증언이나 인간 행동 재현의 증거가 아닙니다. 문제 후보는 사람 검토 전이며, 후보가 없다고 사이트에 문제가 없다는 뜻도 아닙니다. 비교의 mock 결과는 시스템 흐름 검증용이고 페르소나 효과 측정 결과가 아닙니다.

viewport DOM 관찰이며 iframe·canvas·복잡한 shadow DOM·custom combobox·password 입력·독립 scroll/keypress는 아직 미지원입니다. 외부 확인 조건은 특정 화면 상태를 확인하며 모든 사이트 기능이나 실제 상품 데이터의 정답을 보장하지 않습니다. 최종 화면의 점검 결과는 실행 전체의 모든 중간 상태를 검증한 결과와 구분합니다. Slow Loop·Wonder는 기본 비활성이며 비교에서는 persona 정보 누출을 막기 위해 Slow Loop를 비활성으로 제한합니다.

`.env`, API 키, OAuth 토큰, 인증 상태, 원본 개인 문서와 고객 개인정보는 push하지 않습니다.
