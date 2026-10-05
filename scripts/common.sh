#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
export UV_CACHE_DIR="$ROOT_DIR/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$ROOT_DIR/.runtime/python"
export PLAYWRIGHT_BROWSERS_PATH="$ROOT_DIR/.cache/ms-playwright"
export npm_config_cache="$ROOT_DIR/.cache/npm"

fail() {
  printf '\n오류: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 도구가 필요합니다. README의 설치 조건을 확인하세요."
}

check_tools() {
  require_command node
  require_command npm
  require_command uv
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" == "24" ]] || fail "Node.js 24가 필요합니다. 현재 버전: $(node --version)"
}

load_environment() {
  [[ -f "$ROOT_DIR/.env" ]] || fail ".env가 없습니다. 먼저 bash scripts/setup.sh를 실행하세요."
  # .env는 신뢰하는 팀원이 관리하는 로컬 개발 파일이며 shell 문법으로 읽습니다.
  set -a
  source "$ROOT_DIR/.env"
  set +a
  case "${ARTIFACT_DIR:-artifacts}" in
    /*) export ARTIFACT_DIR="${ARTIFACT_DIR}" ;;
    *) export ARTIFACT_DIR="$ROOT_DIR/${ARTIFACT_DIR:-artifacts}" ;;
  esac
}

check_docker() {
  require_command docker
  docker compose version >/dev/null 2>&1 || fail "Docker Compose가 필요합니다. Docker Desktop을 설치/업데이트하세요."
  docker info >/dev/null 2>&1 || fail "Docker가 실행 중인지 확인하세요. Docker Desktop을 켠 뒤 다시 실행하세요."
}

compose() {
  docker compose --project-directory "$ROOT_DIR" -f "$ROOT_DIR/compose.yaml" "$@"
}
