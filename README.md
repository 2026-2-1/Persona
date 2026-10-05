# Persona

화면에서 실행을 요청하면 API가 DB에 세션을 저장하고, Celery 워커가 Playwright로 로컬 시험 페이지를 조작합니다. 결과와 클릭 전·후 스크린샷을 화면에서 확인할 수 있습니다.

현재 행동 계획은 `mock`입니다. 정해진 상품 버튼을 클릭하는 연결 확인용 데모이며, 실제 모델 호출이나 페르소나의 행동 타당성 검증은 아직 구현하지 않았습니다. API 키 없이 실행할 수 있습니다.

macOS에서 백엔드 테스트 24개, 실제 Chromium 테스트 1개, 프런트 검사와 빌드를 통과했습니다. PostgreSQL·Redis를 포함한 전체 연결과 화면에서의 샘플 실행도 확인했습니다. 완료된 실행에는 행동 2개와 화면 기록 3개가 남습니다. [확인한 화면](docs/screenshots/desktop-demo.jpg)과 [모바일 화면](docs/screenshots/mobile-demo.jpg)을 참고할 수 있습니다. GitHub CI는 저장소에 올린 후 실행됩니다.

## 처음 실행하기

먼저 Git, [Node.js 24와 npm](https://nodejs.org/en/download), [uv](https://docs.astral.sh/uv/getting-started/installation/), [Docker Desktop](https://docs.docker.com/desktop/)을 준비합니다. Python은 3.12를 사용하며, 없으면 uv가 프로젝트용으로 설치합니다. macOS와 Linux에서 Bash로 실행하고, Windows에서는 **WSL2 안에 Node와 uv를 설치하고 Docker Desktop의 WSL 통합을 켭니다.**

이 `persona` 폴더에서 실행하세요. 기존 기획자료가 있는 상위 폴더는 개발 저장소에 포함하지 않습니다.

### VS Code에서 시작하기

VS Code의 **파일 → 폴더 열기**에서 이 `persona` 폴더를 선택합니다. `.vscode`에 Python 경로, 추천 확장, 실행 작업을 넣어 두었습니다. Python, Ruff, ESLint 확장을 사용할 수 있습니다. Windows에서는 WSL 창으로 폴더를 엽니다.

Docker Desktop을 켠 뒤 VS Code 터미널에서 아래 설치·실행 명령을 사용합니다. 또는 `Cmd+Shift+P`(Windows/Linux는 `Ctrl+Shift+P`)에서 `Tasks: Run Task`를 찾아 **Persona: 설치**, **Persona: 개발 실행**을 순서대로 실행합니다. 검사와 DB·Redis 종료 작업도 있습니다. Python이 다른 버전으로 선택돼 있으면 `Python: Select Interpreter`에서 `backend/.venv/bin/python`을 선택합니다.

현재 폴더의 샘플 실행을 확인한 다음 아래 GitHub 연결 절차를 진행합니다. 기획자료가 있는 상위 폴더에 Git이 초기화돼 있더라도, 개발 코드용 Git은 `persona` 안에 따로 초기화합니다.

```bash
bash scripts/setup.sh
bash scripts/dev.sh
```

설치는 처음 한 번 필요합니다. `setup.sh`는 기존 `.env`를 보존하고 잠금 파일대로 의존성과 Chromium을 설치합니다. 개발 실행은 DB/Redis 시작, DB 마이그레이션, API/워커/화면 실행까지 처리합니다.

- 개발 화면: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- API 문서: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 로컬 시험 페이지: [http://127.0.0.1:8000/fixtures/shop](http://127.0.0.1:8000/fixtures/shop)

화면에서 데모 실행 버튼을 누릅니다. `queued → running → succeeded`가 되고 클릭 전·후 화면이 나타나면 첫 연결 확인이 완료됩니다. 실행이 실패하면 세션 오류와 `.cache/logs/api.log`, `worker.log`, `web.log`를 확인합니다.

## 검사와 종료

```bash
bash scripts/check.sh
```

위 명령은 백엔드 검사/테스트와 프런트 코드 검사/타입 검사/빌드를 수행합니다. API와 워커를 실행한 상태에서 전체 연결을 추가로 확인하려면 별도 터미널에서 실행합니다.

```bash
uv run --project backend --frozen python scripts/smoke.py
```

`dev.sh` 터미널에서 **Ctrl+C**를 누르면 이번 실행에서 시작한 API/워커/화면 프로세스가 종료됩니다. DB/Redis는 유지합니다. DB/Redis까지 종료하려면 다음을 실행합니다. 저장된 데이터는 삭제하지 않습니다.

```bash
bash scripts/stop.sh
```

## 폴더별 담당

```text
persona/
├── apps/web/                  # Next.js + TypeScript: 실행/상태/결과 화면
├── backend/
│   ├── src/persona/           # FastAPI, DB 모델, 워커, 행동 계획, 브라우저 실행
│   ├── migrations/            # Alembic DB 스키마 변경
│   ├── tests/                 # API/상태 검증, 로컬 브라우저 테스트
│   ├── pyproject.toml
│   └── uv.lock
├── scripts/                   # 설치/실행/검사/종료/통합 확인
├── docs/architecture.md       # 모듈 연결과 API 계약
├── .github/workflows/ci.yml   # PR 코드 검사와 빌드
├── .vscode/                  # Python·확장 설정과 설치/실행/검사 작업
├── compose.yaml               # PostgreSQL 17 + Redis 7
├── .env.example               # 팀 공통 설정 예시
└── artifacts/                 # 생성된 스크린샷; Git에 포함하지 않음
```

| 담당 | 첫 작업과 완료 기준 |
|---|---|
| 프런트 | `apps/web`에서 세션 생성/조회/취소 API 연결 유지, 결과 표시 개선 |
| API·DB | `backend`의 API와 DB 모델 확장, 스키마 변경은 마이그레이션에 기록 |
| 브라우저·모델 | 로컬 시험 페이지 과업 확장, mock 계획기를 실제 모델 어댑터로 교체 |
| 통합 | 설치부터 스크린샷 조회까지 시연, 변경 후 `check.sh`와 통합 확인 |

## 환경변수와 데이터

`.env.example`을 바탕으로 만든 `.env`에서 API/DB/Redis 주소와 CORS를 관리합니다. 스크립트는 `.env`를 Bash 문법으로 읽으므로 신뢰하는 팀원이 관리하는 단순 `KEY=value` 파일로 유지합니다. 값에 공백이 있다면 따옴표로 감싸세요.

- API/화면은 로컬 주소 `127.0.0.1`, DB는 `15432`, Redis는 `16379` 포트를 사용합니다.
- DB 계정 `persona` / `persona_dev`는 로컬 개발 예시입니다. 비밀번호나 포트를 바꾸면 `DATABASE_URL`도 함께 수정합니다.
- DB 계정 설정은 볼륨을 처음 만들 때 적용됩니다. 기존 볼륨의 비밀번호는 `.env` 수정만으로 변경되지 않습니다.
- `.env`, 실행 로그, 스크린샷, 가상환경은 공유하지 않습니다. `uv.lock`과 `package-lock.json`은 커밋합니다.
- 현재 `MODEL_PROVIDER=mock`만 지원합니다. `OPENAI_API_KEY`는 비워두어도 됩니다.

## 실행이 안 될 때

| 증상 | 확인할 내용 |
|---|---|
| Node 버전 오류 | Node 24를 선택합니다. nvm 사용자는 `nvm use` 후 다시 실행합니다. |
| Docker 연결 오류 | Docker Desktop 실행 여부와 Compose 설치를 확인합니다. |
| 8000/3000 포트 사용 중 | 기존 개발 터미널을 Ctrl+C로 종료한 뒤 실행합니다. |
| 15432/16379 포트 충돌 | `.env`의 호스트 포트와 해당 URL을 함께 변경합니다. |
| Chromium 실행 파일 없음 | `bash scripts/setup.sh`를 다시 실행합니다. |
| Linux/WSL 브라우저 라이브러리 오류 | `cd backend` 후 `uv run --frozen playwright install-deps chromium`으로 시스템 라이브러리를 설치합니다. 관리자 권한이 필요할 수 있습니다. [Playwright 안내](https://playwright.dev/python/docs/browsers) |
| DB 마이그레이션 오류 | `DATABASE_URL`, DB/Redis 실행 상태, `.cache/logs`를 확인하고 `dev.sh`를 다시 실행합니다. |
| 세션이 queued에 머묾 | `worker.log`에서 워커 시작과 Redis 연결을 확인합니다. |
| 브라우저에서 CORS 오류 | 접속한 화면 주소가 `CORS_ORIGINS`에 있는지 확인한 후 API를 재시작합니다. |

## 공개 GitHub 저장소에 올리기

[2026-2-1 조직](https://github.com/2026-2-1)에 이름 `persona`의 **빈 Public 저장소**를 만듭니다. 아래는 저장소 이름을 `persona`로 정한 경우의 명령입니다. GitHub에서 README/라이선스/ignore를 미리 만들지 않아야 그대로 사용할 수 있습니다.

현재 상위 폴더에는 기획자료가 있으므로 반드시 이 `persona` 폴더 안에서 진행합니다. 아래 명령은 업로드 준비 안내이며 자동으로 실행하지 않습니다.

```bash
git init -b main
git rev-parse --show-toplevel
git add .
git status --short
git commit -m "chore: bootstrap persona development environment"
git remote add origin https://github.com/2026-2-1/persona.git
git push -u origin main
```

`git rev-parse --show-toplevel`이 `persona` 폴더를 가리키는지 먼저 확인합니다. `git status`에서 `.env`, `.cache`, `.runtime`, `artifacts`, `node_modules`가 제외됐는지 확인한 뒤 커밋합니다. 조직 저장소 이름이 다르면 원격 URL을 그 이름으로 바꿉니다. 팀원은 저장소를 복제해 동일한 설치/실행 명령을 사용합니다. PR과 main 푸시에서 CI가 동작합니다.

자세한 연결 구조는 [architecture.md](docs/architecture.md), 협업 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
