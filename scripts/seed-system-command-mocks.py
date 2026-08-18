"""Seed deterministic system CLI commands for local mock workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def request(base_url: str, admin_key: str, method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"X-SkillHub-Admin-Key": admin_key, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method), timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接 API {base_url}: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=None, help="SkillHub API 地址，默认读取 SKILLHUB_API_PORT")
    parser.add_argument("--fixture", type=Path, default=None, help="系统命令 fixture JSON 路径")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_env(root)
    port = os.environ.get("SKILLHUB_API_PORT", "8000")
    base_url = args.api_url or f"http://127.0.0.1:{port}"
    admin_key = os.environ.get("SKILLHUB_ADMIN_CONSOLE_KEY", "")
    if not admin_key:
        raise SystemExit("SKILLHUB_ADMIN_CONSOLE_KEY is required")
    fixture = args.fixture or root / "apps/backend/tests/fixtures/system-command-library-mock.json"
    commands = json.loads(fixture.read_text(encoding="utf-8"))
    existing = request(base_url, admin_key, "GET", "/api/admin/system-commands").get("commands", [])
    by_id = {item.get("id"): item for item in existing}
    for command in commands:
        command_id = command["id"]
        if command_id in by_id:
            update_payload = {key: value for key, value in command.items() if key != "id"}
            request(base_url, admin_key, "PUT", f"/api/admin/system-commands/{command_id}", update_payload)
            print(f"updated {command_id}")
        else:
            request(base_url, admin_key, "POST", "/api/admin/system-commands", command)
            print(f"created {command_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
