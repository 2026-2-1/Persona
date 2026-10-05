#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ROOT_DIR"
check_docker
printf 'PostgreSQL/Redis 컨테이너를 종료합니다. 저장된 데이터는 유지합니다.\n'
compose down
printf '실행 중인 dev.sh 터미널에서도 Ctrl+C를 눌러 API/워커/화면을 종료하세요.\n'
