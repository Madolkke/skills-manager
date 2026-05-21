#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${SKILLHUB_API_PORT:-8000}"
WEB_PORT="${SKILLHUB_WEB_PORT:-3030}"
DATA_DIR="${SKILLHUB_DATA_DIR:-$ROOT_DIR/.data}"
DATABASE_URL="${SKILLHUB_DATABASE_URL:-sqlite:///$DATA_DIR/skillhub.sqlite3}"
export UV_NO_CACHE="${UV_NO_CACHE:-1}"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting SkillHub API on http://127.0.0.1:${API_PORT}"
mkdir -p "$DATA_DIR"
(
  cd "$ROOT_DIR/apps/api"
  SKILLHUB_DATABASE_URL="$DATABASE_URL" uv run uvicorn skillhub.api.main:app --host 127.0.0.1 --port "$API_PORT"
) &
API_PID=$!

if [[ ! -d "$ROOT_DIR/apps/web-v4/node_modules" ]]; then
  echo "Installing web dependencies in apps/web-v4"
  (
    cd "$ROOT_DIR/apps/web-v4"
    npm install
  )
fi

echo "Starting SkillHub web v4 on http://127.0.0.1:${WEB_PORT}/skills"
(
  cd "$ROOT_DIR/apps/web-v4"
  VITE_SKILLHUB_API_URL="http://127.0.0.1:${API_PORT}" npm run dev -- --host 127.0.0.1 --port "$WEB_PORT"
) &
WEB_PID=$!

echo "SkillHub web v4 is starting. Open http://127.0.0.1:${WEB_PORT}/skills"
while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID"
    exit $?
  fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    wait "$WEB_PID"
    exit $?
  fi
  sleep 1
done
