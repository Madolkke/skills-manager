#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${SKILLHUB_API_PORT:-8000}"
WEB_PORT="${SKILLHUB_WEB_PORT:-3030}"
HOST="${SKILLHUB_HOST:-127.0.0.1}"
export UV_NO_CACHE="${UV_NO_CACHE:-1}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

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
if [[ -z "${SKILLHUB_DATABASE_URL:-}" ]]; then
  echo "SKILLHUB_DATABASE_URL is required. Example: postgresql+psycopg://postgres@127.0.0.1:5432/skillhub" >&2
  exit 1
fi
(
  cd "$ROOT_DIR/apps/backend"
  uv run python -m skillhub.models.schema.cli upgrade
)
(
  cd "$ROOT_DIR/apps/backend"
  SKILLHUB_DATABASE_URL="$SKILLHUB_DATABASE_URL" uv run uvicorn skillhub.bootstrap.app:create_app --factory --host "$HOST" --port "$API_PORT"
) &
API_PID=$!

if [[ ! -d "$ROOT_DIR/apps/frontend/node_modules" ]]; then
  echo "Installing web dependencies in apps/frontend"
  (
    cd "$ROOT_DIR/apps/frontend"
    npm install
  )
fi

echo "Starting SkillHub web on http://${HOST}:${WEB_PORT}/skills"
(
  cd "$ROOT_DIR/apps/frontend"
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
