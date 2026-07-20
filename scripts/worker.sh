#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$#" -gt 1 ]]; then
  echo "Usage: $0 <worker-id>" >&2
  exit 2
fi
WORKER_ID_OVERRIDE="${1-}"
if [[ "$#" -eq 1 && -z "$WORKER_ID_OVERRIDE" ]]; then
  echo "worker-id must not be empty." >&2
  exit 2
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ "$#" -eq 1 ]]; then
  export EVAL_RUNNER_WORKER_ID="$WORKER_ID_OVERRIDE"
fi

if [[ -z "${SKILLHUB_DATABASE_URL:-}" ]]; then
  echo "SKILLHUB_DATABASE_URL is required." >&2
  exit 1
fi

export OPENCODE_BASE_URL="${OPENCODE_BASE_URL:-http://127.0.0.1:4096}"
export EVAL_WORKDIR_HOST="${EVAL_WORKDIR_HOST:-$ROOT_DIR/.data/eval-runs}"
if [[ "$EVAL_WORKDIR_HOST" != /* ]]; then
  export EVAL_WORKDIR_HOST="$ROOT_DIR/$EVAL_WORKDIR_HOST"
fi
mkdir -p "$EVAL_WORKDIR_HOST"

cd "$ROOT_DIR/apps/backend"
uv run python -m skillhub_worker.main
