from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerConfig:
    opencode_base_url: str
    laminar_base_url: str
    laminar_http_port: int | None
    laminar_project_api_key: str | None
    workdir_host: Path
    workdir_container: str
    poll_interval_seconds: float
    timeout_seconds: float
    max_attempts: int
    worker_id: str
    stale_after_seconds: int = 360
    publish_release_timeout_seconds: float = 120


def load_config() -> WorkerConfig:
    timeout_seconds = float(os.environ.get("EVAL_RUNNER_TIMEOUT_SECONDS", "300"))
    return WorkerConfig(
        opencode_base_url=os.environ.get("OPENCODE_BASE_URL", "http://opencode:4096").rstrip("/"),
        laminar_base_url=_laminar_base_url(),
        laminar_http_port=_optional_int(os.environ.get("LMNR_HTTP_PORT")),
        laminar_project_api_key=os.environ.get("LMNR_PROJECT_API_KEY"),
        workdir_host=Path(os.environ.get("EVAL_WORKDIR_HOST", "/var/lib/skillhub/eval-runs")).resolve(),
        workdir_container=os.environ.get("EVAL_WORKDIR_CONTAINER", "/workspace/eval-runs").rstrip("/"),
        poll_interval_seconds=float(os.environ.get("EVAL_RUNNER_POLL_SECONDS", "2")),
        timeout_seconds=timeout_seconds,
        max_attempts=max(1, int(os.environ.get("EVAL_RUNNER_MAX_ATTEMPTS", "2"))),
        worker_id=os.environ.get("EVAL_RUNNER_WORKER_ID", "opencode-worker"),
        stale_after_seconds=max(
            1,
            int(os.environ.get("WORKER_JOB_STALE_AFTER_SECONDS", str(max(int(timeout_seconds + 60), 360)))),
        ),
        publish_release_timeout_seconds=max(
            1,
            float(os.environ.get("PUBLISH_RELEASE_TIMEOUT_SECONDS", "120")),
        ),
    )


def _laminar_base_url() -> str:
    base = os.environ.get("LMNR_BASE_URL", "https://api.lmnr.ai").rstrip("/")
    return base


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)
