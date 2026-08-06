from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from os import environ
from typing import Callable, Mapping

from skillhub.services.workflow_executor_client import WorkflowExecutorClient


@dataclass(frozen=True, slots=True)
class WorkflowDebugSettings:
    executor_base_url: str | None
    request_timeout_seconds: float = 10
    poll_interval_seconds: float = 2
    max_duration_seconds: float = 300

    @classmethod
    def from_environ(cls, values: Mapping[str, str] = environ) -> "WorkflowDebugSettings":
        base_url = values.get("WORKFLOW_EXECUTOR_BASE_URL", "").strip() or None
        return cls(
            executor_base_url=base_url,
            request_timeout_seconds=_positive_float(values, "WORKFLOW_EXECUTOR_REQUEST_TIMEOUT_SECONDS", 10),
            poll_interval_seconds=_positive_float(values, "WORKFLOW_DEBUG_POLL_INTERVAL_SECONDS", 2),
            max_duration_seconds=_positive_float(values, "WORKFLOW_DEBUG_MAX_DURATION_SECONDS", 300),
        )


ExecutorClientFactory = Callable[[str, float], WorkflowExecutorClient]


def create_executor_client(base_url: str, timeout_seconds: float) -> WorkflowExecutorClient:
    return WorkflowExecutorClient(base_url=base_url, timeout_seconds=timeout_seconds)


def encode_run_cursor(created_at: datetime, run_id: str) -> str:
    value = f"{created_at.isoformat()}\n{run_id}".encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_run_cursor(value: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(value) % 4)
        created_at, run_id = base64.urlsafe_b64decode(value + padding).decode().split("\n", 1)
        parsed = datetime.fromisoformat(created_at)
        if parsed.tzinfo is None or not run_id:
            raise ValueError
        return parsed, run_id
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid Workflow debug run cursor.") from exc


def public_debug_run(row: dict, *, poll_interval_seconds: float = 2) -> dict:
    keys = (
        "id",
        "case_id",
        "skill_id",
        "step_id",
        "status",
        "passed",
        "task_id",
        "executor_run_id",
        "workflow_revision",
        "workflow_digest",
        "expected_target_id",
        "error",
        "created_at",
        "updated_at",
        "completed_at",
    )
    return {key: row.get(key) for key in keys} | {
        "latest_executor_status": row.get("executor_status"),
        "poll_interval_seconds": poll_interval_seconds,
    }


def public_debug_case(row: dict) -> dict:
    keys = (
        "id",
        "skill_id",
        "step_id",
        "name",
        "description",
        "expected_target_id",
        "workflow_inputs",
        "collection_fixtures",
        "created_at",
        "updated_at",
    )
    return {key: row[key] for key in keys}


def _positive_float(values: Mapping[str, str], key: str, default: float) -> float:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero.")
    return value


__all__ = [
    "ExecutorClientFactory",
    "WorkflowDebugSettings",
    "create_executor_client",
    "decode_run_cursor",
    "encode_run_cursor",
    "public_debug_run",
    "public_debug_case",
]
