#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${SKILLHUB_WEB_FLAVOR:-formal}" == "legacy" ]]; then
  exec bash "$ROOT_DIR/scripts/dev-legacy-web.sh" "$@"
fi

exec bash "$ROOT_DIR/scripts/dev-v4.sh" "$@"
