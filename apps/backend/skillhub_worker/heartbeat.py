from __future__ import annotations

import logging
from typing import Any

from skillhub.models.entities import utc_now
from skillhub.models.store import SkillHubStore

WORKER_STARTED_AT = utc_now()
logger = logging.getLogger(__name__)


def record_idle(store: SkillHubStore, *, config) -> None:
    """Record that a worker is alive and not currently running a job."""
    _record_worker_heartbeat(
        store,
        worker_id=config.worker_id,
        status="idle",
        metadata=_metadata(config),
        started_at=WORKER_STARTED_AT,
    )


def record_eval_running(store: SkillHubStore, detail: dict[str, Any], *, config) -> None:
    """Record the eval case run job currently owned by a worker."""
    job = detail.get("job") or {}
    run = detail["eval_case_run"]
    _record_worker_heartbeat(
        store,
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
    _record_worker_heartbeat(
        store,
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
    _record_worker_heartbeat(
        store,
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


def renew_execution_lease(store: SkillHubStore, execution: dict[str, Any]) -> bool:
    """Best-effort renewal; a stale execution must not terminate the worker."""
    if not execution:
        return True
    try:
        return store.renew_job_lease(
            job_id=str(execution["job_id"]),
            worker_id=str(execution["worker_id"]),
            attempt=int(execution["attempt"]),
        )
    except Exception:
        logger.exception("job heartbeat failed job_id=%s", execution.get("job_id"))
        return False


def _record_worker_heartbeat(store: SkillHubStore, **kwargs: Any) -> None:
    try:
        store.record_worker_heartbeat(**kwargs)
    except Exception:
        logger.exception("worker heartbeat failed worker_id=%s status=%s", kwargs.get("worker_id"), kwargs.get("status"))
