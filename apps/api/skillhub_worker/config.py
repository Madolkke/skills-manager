from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class WorkerConfig:
    opencode_base_url: str
    workdir_host: Path
    workdir_container: str
    poll_interval_seconds: float
    timeout_seconds: float
    max_attempts: int
    worker_id: str


def load_config() -> WorkerConfig:
    return WorkerConfig(
        opencode_base_url=os.environ.get("OPENCODE_BASE_URL", "http://opencode:4096").rstrip("/"),
        workdir_host=Path(os.environ.get("EVAL_WORKDIR_HOST", "/var/lib/skillhub/eval-runs")).resolve(),
        workdir_container=os.environ.get("EVAL_WORKDIR_CONTAINER", "/workspace/eval-runs").rstrip("/"),
        poll_interval_seconds=float(os.environ.get("EVAL_RUNNER_POLL_SECONDS", "2")),
        timeout_seconds=float(os.environ.get("EVAL_RUNNER_TIMEOUT_SECONDS", "300")),
        max_attempts=max(1, int(os.environ.get("EVAL_RUNNER_MAX_ATTEMPTS", "2"))),
        worker_id=os.environ.get("EVAL_RUNNER_WORKER_ID", "opencode-worker"),
    )
