#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ROOT_DIR"
check_tools
printf '백엔드 코드 검사와 테스트를 실행합니다.\n'
(cd backend && uv run --frozen ruff check . && uv run --frozen pytest)
printf '\n프런트엔드 코드/타입 검사와 빌드를 실행합니다.\n'
npm run lint --prefix apps/web
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
printf '\n모든 검사를 통과했습니다.\n'
