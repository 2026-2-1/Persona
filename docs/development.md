# 개발 환경과 협업

## GPU 서버 Qwen 연결

1. 로그인 서버에서 Slurm GPU를 할당받고 DIS01의 `~/persona-llm`에서 `source .venv-dis01/bin/activate`, `export HF_HUB_OFFLINE=1`, `python -u api_server.py`를 실행한다. 서버와 할당 세션을 유지한다.
2. 로컬 별도 터미널에서 기존 SSH 점프 경로로 DIS01의 8000번 포트를 전달한다. SSH 비밀번호는 터미널에 직접 입력하거나 SSH 키를 사용한다. 프로젝트 `.env`에 SSH 비밀번호를 저장하지 않는다.
3. 로컬에서 `curl http://127.0.0.1:8000/health`로 `model: persona-qwen`을 확인한다. 터널의 로컬 포트를 바꾼 경우 `.env`의 `PERSONA_QWEN_API_URL=http://127.0.0.1:<포트>/v1/chat/completions`를 설정한다. URL은 로컬 주소만 허용한다.
4. 대시보드의 GPU 서버 제공자를 선택하고 **연결 확인**을 누른다. 키 입력은 없다. CLI는 `python3 -m uxagent run --study configs/study-decathlon-live.json --provider gpu --headless`처럼 실행한다. 이 공개 사이트 설정은 검색 결과와 상세 일부만 독립 판정한다.
5. Slurm 할당이 끝나거나 SSH 터널이 닫히면 이후 모델 요청은 실패한다. 앱의 연결 확인은 원격 할당이나 터널을 자동 시작하지 않는다.

기본 합성 fixture는 로컬 8000번 포트를 사용한다. 합성 fixture와 GPU 모델을 함께 실행할 때는 터널을 로컬 8001번 등으로 열고 `PERSONA_QWEN_API_URL`을 같은 포트로 지정한다. 원격 서버의 포트는 계속 8000번이다. 이 GPU 제공자의 임베딩 API와 모델 비용은 확인되지 않았으므로 임베딩 설정을 사용하지 않고 비용은 미확인으로 남긴다.

## Windows PowerShell

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m uxagent doctor --study configs/study.json
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check_repo.py
.venv/Scripts/python.exe -m uxagent run --study configs/study.json --provider mock --headless
.venv/Scripts/python.exe -m uxagent dashboard
```

대시보드: http://127.0.0.1:8765. Mock은 키가 필요 없다. 키가 필요한 실험에서는 .env.example의 빈 변수를 로컬 .env에 설정한다. 예시 파일에 키를 넣지 않는다.

## macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_repo.py
```

## 한 이슈의 작업 흐름

브랜치·커밋은 [협업 규칙](collaboration.md)을 따른다.

첫 checkout에서 `git config core.hooksPath .githooks`를 실행하면 커밋 전에 staged 경로·민감정보·문서 링크 검사를 자동 실행한다. CI에서도 같은 검사를 수행한다.

1. 이슈의 선행 작업·문서·완료 조건·회귀 검사를 읽는다.
2. prototype 최신 상태에서 feat/<issue>-<topic> 또는 fix/<issue>-<topic> 브랜치를 만든다.
3. 관련 실패 사례를 테스트로 재현하고 최소 변경으로 통과시킨다.
4. 관련 테스트와 전체 pytest, repo 검사, mock 통합을 수행한다. 문서만 변경하면 repo 검사와 링크를 확인한다.
5. docs/current-state.md·트러블슈팅·검증 기록·README를 필요한 만큼 갱신한다.
6. 변경 파일을 명시적으로 stage한다. `git add .`로 인증파일을 함께 올리지 않는다.
7. `python scripts/check_repo.py --staged`와 staged 목록을 확인하고 커밋·push한다.
8. prototype 대상 PR에 이슈 링크, 실제 검사 결과, 남은 제한을 적고 리뷰받는다.

GitHub Actions는 Windows/Python 3.13, Ubuntu/Python 3.11에서 pytest·repo 검사·doctor·mock을 실행한다. API 비밀값과 라이브 API 호출은 CI에 넣지 않는다. CI는 prototype·feat/**·fix/**·chore/**·codex/** push, prototype/main 대상 PR 및 수동 실행으로 동작한다. 기능 브랜치를 대상으로 하는 PR도 head 브랜치 push 검사로 검증한다. main의 기존 설정을 변경하지 않는다.

scripts/check_repo.py는 선택한 Git 파일의 민감 경로·일부 credential 패턴과 Markdown 로컬 링크를 검사하는 보조 장치다. 모든 비밀을 검출하는 보장은 없으므로 직접 검토도 수행한다.

## API 없는 시나리오 검사

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_extended_actions.py tests/test_decathlon_evaluator.py tests/test_offline_scenarios.py
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-flow.json --defect filter
.venv/Scripts/python.exe -m uxagent scenario --config configs/scenarios/decathlon-reset.json --defect reset
```

대시보드의 `API 없는 과업 점검`은 별도 API 연결 없이 기록·개선 보드·내보내기로 이어진다. [사용법](offline-scenarios.md)에 네 합성 과업과 실제 공개 부분 검증을 구분한다. live config는 CI 기본 검사가 아니며 상품/사이트 변경 때문에 결과를 보장하지 않는다. `summary.json`의 판정·체크·종료 사유를 확인하고 실제 결과를 verification.md에 기록한다. CLI 종료 코드 0이 과업 성공을 뜻하지 않는다.
