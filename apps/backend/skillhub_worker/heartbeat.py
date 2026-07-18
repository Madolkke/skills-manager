from __future__ import annotations

from typing import Any

from skillhub.models.entities import utc_now
from skillhub.models.store import SkillHubStore

WORKER_STARTED_AT = utc_now()


def record_idle(store: SkillHubStore, *, config) -> None:
    """Record that a worker is alive and not currently running a job."""
    store.record_worker_heartbeat(
        worker_id=config.worker_id,
        status="idle",
        metadata=_metadata(config),
        started_at=WORKER_STARTED_AT,
    )


def record_eval_running(store: SkillHubStore, detail: dict[str, Any], *, config) -> None:
    """Record the eval case run job currently owned by a worker."""
    job = detail.get("job") or {}
    run = detail["eval_case_run"]
    store.record_worker_heartbeat(
        worker_id=config.worker_id,
        status="running",
        current_job_id=str(job.get("id") or ""),
        current_job_type=str(job.get("type") or "eval_case_run"),
        current_run_id=str(run["id"]),
        metadata=_metadata(config),
        started_at=WORKER_STARTED_AT,
    )


def record_builder_running(store: SkillHubStore, detail: dict[str, Any], *, config) -> None:
    """Record the skill builder job currently owned by a worker."""
    job = detail["job"]
    session = detail["session"]
    store.record_worker_heartbeat(
        worker_id=config.worker_id,
        status="running",
        current_job_id=str(job["id"]),
        current_job_type=str(job.get("type") or "skill_builder_message"),
        current_session_id=str(session["id"]),
        metadata=_metadata(config),
        started_at=WORKER_STARTED_AT,
    )


def record_publish_running(store: SkillHubStore, detail: dict[str, Any], *, config) -> None:
    """Record the publish release job currently owned by a worker."""
    job = detail["job"]
    store.record_worker_heartbeat(
        worker_id=config.worker_id,
        status="running",
        current_job_id=str(job["id"]),
        current_job_type=str(job.get("type") or "publish_release"),
        metadata=_metadata(config),
        started_at=WORKER_STARTED_AT,
    )


def _metadata(config) -> dict[str, Any]:
    return {
        "opencode_base_url": config.opencode_base_url,
        "workdir_host": str(config.workdir_host),
        "max_attempts": config.max_attempts,
    }
