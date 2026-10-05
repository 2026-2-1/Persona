#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ROOT_DIR"
check_tools
load_environment
check_docker
[[ -d backend/.venv && -d apps/web/node_modules ]] || fail "의존성이 없습니다. 먼저 bash scripts/setup.sh를 실행하세요."
mkdir -p .cache/logs "$ARTIFACT_DIR"

printf 'PostgreSQL과 Redis를 준비합니다.\n'
compose up -d --wait --wait-timeout 60
printf 'DB 스키마를 최신 상태로 맞춥니다.\n'
(cd backend && uv run --frozen alembic upgrade head)
printf 'API, 작업 워커, 개발 화면을 시작합니다.\n'
exec uv run --project backend --frozen python "$ROOT_DIR/scripts/run_services.py"
