from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select, update

from skillhub.models.entities import utc_now
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class JobLeaseMixin:
    def renew_job_lease(self, *, job_id: str, worker_id: str, attempt: int) -> bool:
        """Renew a running Job only when the caller still owns its attempt."""
        with self._write_session() as connection:
            result = connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job_id)
                .where(orm.Job.status == "running")
                .where(orm.Job.locked_by == worker_id)
                .where(orm.Job.attempts == attempt)
                .values(last_heartbeat_at=utc_now())
            )
            owned = result.rowcount == 1
        if not owned:
            logger.warning(
                "job.late_result_ignored action=heartbeat job_id=%s worker_id=%s attempt=%s",
                job_id,
                worker_id,
                attempt,
            )
        return owned

    def recover_stale_jobs(self, *, stale_after_seconds: int, max_eval_attempts: int) -> dict[str, int]:
        """Recover expired Eval leases and fail uncertain Publish leases."""
        now = utc_now()
        cutoff = now - timedelta(seconds=stale_after_seconds)
        recovered = {"eval_requeued": 0, "eval_failed": 0, "publish_failed": 0}
        with self._write_session() as connection:
            jobs = (
                connection.execute(
                    orm.select_entity(orm.Job)
                    .where(orm.Job.status == "running")
                    .where(orm.Job.type.in_(["eval_case_run", "publish_release"]))
                    .where(or_(orm.Job.last_heartbeat_at.is_(None), orm.Job.last_heartbeat_at < cutoff))
                    .order_by(orm.Job.created_at, orm.Job.id)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            for job in jobs:
                logger.warning(
                    "job.lease_expired job_id=%s type=%s worker_id=%s attempt=%s",
                    job["id"],
                    job["type"],
                    job["locked_by"],
                    job["attempts"],
                )
                payload = dict(job["payload"] or {})
                if job["type"] == "eval_case_run":
                    self._recover_stale_eval_job(connection, job, payload, now, max_eval_attempts, recovered)
                else:
                    self._fail_stale_publish_job(connection, job, payload, now, recovered)
        return recovered

    def _lock_owned_job(self, connection, *, job_id: str, worker_id: str, attempt: int):
        job = (
            connection.execute(
                orm.select_entity(orm.Job)
                .where(orm.Job.id == job_id)
                .where(orm.Job.status == "running")
                .where(orm.Job.locked_by == worker_id)
                .where(orm.Job.attempts == attempt)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if job is None:
            logger.warning(
                "job.late_result_ignored job_id=%s worker_id=%s attempt=%s",
                job_id,
                worker_id,
                attempt,
            )
        return job

    def _recover_stale_eval_job(self, connection, job, payload: dict[str, Any], now, max_attempts: int, recovered) -> None:
        run_id = str(payload.get("eval_case_run_id") or "")
        message = f"Worker lease expired after attempt {job['attempts']}."
        if job["attempts"] < max_attempts:
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job["id"])
                .values(status="queued", locked_by=None, last_heartbeat_at=None, error=message, finished_at=None)
            )
            connection.execute(
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == run_id)
                .where(orm.EvalCaseRun.status == "running")
                .values(status="queued", started_at=None, finished_at=None, error=message)
            )
            recovered["eval_requeued"] += 1
            logger.warning("job.requeued job_id=%s eval_case_run_id=%s attempt=%s", job["id"], run_id, job["attempts"])
            return
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job["id"])
            .values(status="failed", locked_by=None, last_heartbeat_at=now, finished_at=now, error=message)
        )
        connection.execute(
            update(orm.EvalCaseRun)
            .where(orm.EvalCaseRun.id == run_id)
            .where(orm.EvalCaseRun.status == "running")
            .values(status="failed", finished_at=now, error=message)
        )
        recovered["eval_failed"] += 1

    def _fail_stale_publish_job(self, connection, job, payload: dict[str, Any], now, recovered) -> None:
        record_id = str(payload.get("publish_record_id") or "")
        message = f"Worker lease expired during publish attempt {job['attempts']}; external state is unknown."
        record = connection.execute(select(orm.PublishRecord).where(orm.PublishRecord.id == record_id).with_for_update()).scalar_one_or_none()
        if record is not None and record.status == "releasing":
            metadata = dict(record.metadata_payload or {})
            metadata.update({"external_state": "unknown", "release_error": message, "lease_expired": True})
            record.status = "failed"
            record.metadata_payload = metadata
            record.confirmed_at = now
            record.confirmed_by = str(job["locked_by"] or "worker:unknown")
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job["id"])
            .values(status="failed", locked_by=None, last_heartbeat_at=now, finished_at=now, error=message)
        )
        recovered["publish_failed"] += 1
        logger.error("publish.external_state_unknown job_id=%s publish_record_id=%s", job["id"], record_id)
