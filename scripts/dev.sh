#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${SKILLHUB_API_PORT:-8000}"
WEB_PORT="${SKILLHUB_WEB_PORT:-3030}"
HOST="${SKILLHUB_HOST:-127.0.0.1}"
DATA_DIR="${SKILLHUB_DATA_DIR:-$ROOT_DIR/.data}"
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

echo "Starting SkillHub API on http://${HOST}:${API_PORT}"
mkdir -p "$DATA_DIR"
API_DATA_DIR="$DATA_DIR"
if command -v cygpath >/dev/null 2>&1; then
  API_DATA_DIR="$(cygpath -w "$DATA_DIR")"
fi
(
  cd "$ROOT_DIR/apps/api"
  if [[ -n "${SKILLHUB_DATABASE_URL:-}" ]]; then
    SKILLHUB_DATABASE_URL="$SKILLHUB_DATABASE_URL" uv run uvicorn skillhub.api.main:app --host "$HOST" --port "$API_PORT"
  else
    SKILLHUB_DATA_DIR="$API_DATA_DIR" uv run uvicorn skillhub.api.main:app --host "$HOST" --port "$API_PORT"
  fi
) &
API_PID=$!

if [[ ! -d "$ROOT_DIR/apps/web/node_modules" ]]; then
  echo "Installing web dependencies in apps/web"
  (
    cd "$ROOT_DIR/apps/web"
    npm install
  )
fi

echo "Starting SkillHub web on http://${HOST}:${WEB_PORT}/skills"
(
  cd "$ROOT_DIR/apps/web"
  if [[ -n "${VITE_SKILLHUB_API_URL:-}" ]]; then
    VITE_SKILLHUB_API_URL="$VITE_SKILLHUB_API_URL" npm run dev -- --host "$HOST" --port "$WEB_PORT"
  else
    VITE_SKILLHUB_API_PORT="$API_PORT" npm run dev -- --host "$HOST" --port "$WEB_PORT"
  fi
) &
WEB_PID=$!

echo "SkillHub web is starting. Open http://127.0.0.1:${WEB_PORT}/skills locally."
if [[ "$HOST" == "0.0.0.0" ]]; then
  echo "For LAN users, open http://<this-computer-lan-ip>:${WEB_PORT}/skills."
fi
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
