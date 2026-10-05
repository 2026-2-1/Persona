#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ROOT_DIR"
check_tools

if [[ ! -f .env ]]; then
  cp .env.example .env
  printf '.env.example을 복사해 .env를 만들었습니다.\n'
else
  printf '기존 .env를 유지합니다.\n'
fi
mkdir -p "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" "$PLAYWRIGHT_BROWSERS_PATH" .cache/logs artifacts
[[ -f backend/uv.lock ]] || fail "backend/uv.lock이 없습니다. 잠금 파일이 포함된 저장소를 받아주세요."
[[ -f apps/web/package-lock.json ]] || fail "apps/web/package-lock.json이 없습니다. 잠금 파일이 포함된 저장소를 받아주세요."

printf '\n백엔드 의존성을 설치합니다. Python 3.12가 없으면 uv가 준비합니다.\n'
uv sync --project backend --frozen
printf '\n프런트엔드 의존성을 설치합니다.\n'
npm ci --prefix apps/web --cache "$ROOT_DIR/.cache/npm" --no-audit --no-fund
printf '\nPlaywright Chromium을 준비합니다.\n'
uv run --project backend --frozen playwright install chromium

if ! command -v docker >/dev/null 2>&1; then
  printf '\n의존성 설치는 완료했습니다. 실행 전 Docker Desktop을 설치하고 켜주세요.\n'
elif ! docker compose version >/dev/null 2>&1; then
  printf '\n의존성 설치는 완료했습니다. 실행 전 Docker Compose를 준비해주세요.\n'
elif ! docker info >/dev/null 2>&1; then
  printf '\n의존성 설치는 완료했습니다. 실행 전 Docker Desktop을 켜주세요.\n'
else
  printf '\n설치 완료. bash scripts/dev.sh로 개발 환경을 시작하세요.\n'
fi
