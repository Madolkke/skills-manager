from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.skill_builder.constants import BUILDER_JOB_TYPE
from skillhub.models.schema import orm

ONLINE_THRESHOLD_SECONDS = 30
ACTIVE_WINDOW_HOURS = 24
WORKER_STATUSES = {"idle", "running"}
SAFE_WORKER_METADATA_KEYS = {"opencode_base_url", "workdir_host", "max_attempts"}


class WorkerStatusMixin:
    def record_worker_heartbeat(
        self,
        *,
        worker_id: str,
        status: str,
        current_job_id: str | None = None,
        current_job_type: str | None = None,
        current_run_id: str | None = None,
        current_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        started_at=None,
    ) -> None:
        """Upsert one worker heartbeat snapshot."""
        clean_worker_id = worker_id.strip()
        if not clean_worker_id:
            raise InvariantError("Worker id cannot be blank.")
        if status not in WORKER_STATUSES:
            raise InvariantError(f"Unknown worker status: {status}")
        now = utc_now()
        values = {
            "worker_id": clean_worker_id,
            "status": status,
            "current_job_id": current_job_id,
            "current_job_type": current_job_type,
            "current_run_id": current_run_id,
            "current_session_id": current_session_id,
            "last_seen_at": now,
            "started_at": started_at or now,
            "metadata_payload": self._canonical_json_object(metadata or {}),
        }
        statement = insert(orm.WorkerHeartbeat).values(**values)
        update_values = {
            getattr(orm.WorkerHeartbeat, key): value
            for key, value in values.items()
            if key != "worker_id"
        }
        with self._write_session() as connection:
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[orm.WorkerHeartbeat.worker_id],
                    set_=update_values,
                )
            )

    def admin_worker_status_overview(self) -> dict[str, Any]:
        """Return recent worker heartbeats and queue summary for the admin UI."""
        now = utc_now()
        active_cutoff = now - timedelta(hours=ACTIVE_WINDOW_HOURS)
        online_cutoff = now - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)
        with self._write_session() as connection:
            heartbeat_rows = (
                connection.execute(
                    orm.select_entity(orm.WorkerHeartbeat)
                    .where(orm.WorkerHeartbeat.last_seen_at >= active_cutoff)
                    .order_by(orm.WorkerHeartbeat.last_seen_at.desc(), orm.WorkerHeartbeat.worker_id)
                )
                .mappings()
                .all()
            )
            job_rows = self._worker_current_jobs(connection, heartbeat_rows)
            eval_rows = self._worker_eval_runs(connection, heartbeat_rows, job_rows)
            summary = self._worker_queue_summary(connection)
        workers = [self._worker_status(row, job_rows, eval_rows, online_cutoff) for row in heartbeat_rows]
        return {
            "generated_at": now,
            "online_threshold_seconds": ONLINE_THRESHOLD_SECONDS,
            "active_window_hours": ACTIVE_WINDOW_HOURS,
            "summary": {
                "total": len(workers),
                "online": sum(1 for worker in workers if worker["online"]),
                "running": sum(1 for worker in workers if worker["status"] == "running"),
                "idle": sum(1 for worker in workers if worker["status"] == "idle"),
                "offline": sum(1 for worker in workers if worker["status"] == "offline"),
                **summary,
            },
            "workers": workers,
        }

    def _worker_current_jobs(self, connection, heartbeat_rows) -> dict[str, dict[str, Any]]:
        job_ids = [row["current_job_id"] for row in heartbeat_rows if row["current_job_id"]]
        if not job_ids:
            return {}
        rows = connection.execute(orm.select_entity(orm.Job).where(orm.Job.id.in_(job_ids))).mappings().all()
        return {row["id"]: self._row_dict(row) for row in rows}

    def _worker_eval_runs(self, connection, heartbeat_rows, job_rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        run_ids = {str(row["current_run_id"]) for row in heartbeat_rows if row["current_run_id"]}
        for job in job_rows.values():
            payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
            if job.get("type") == "eval_case_run" and payload.get("eval_case_run_id"):
                run_ids.add(str(payload["eval_case_run_id"]))
        if not run_ids:
            return {}
        rows = connection.execute(orm.select_entity(orm.EvalCaseRun).where(orm.EvalCaseRun.id.in_(run_ids))).mappings().all()
        return {row["id"]: self._row_dict(row) for row in rows}

    def _worker_queue_summary(self, connection) -> dict[str, int]:
        rows = connection.execute(
            select(orm.Job.type, orm.Job.status, func.count().label("count"))
            .where(orm.Job.type.in_(["eval_case_run", BUILDER_JOB_TYPE]))
            .where(orm.Job.status.in_(["queued", "running"]))
            .group_by(orm.Job.type, orm.Job.status)
        ).mappings().all()
        counts = {(row["type"], row["status"]): int(row["count"]) for row in rows}
        return {
            "queued_eval_jobs": counts.get(("eval_case_run", "queued"), 0),
            "queued_builder_jobs": counts.get((BUILDER_JOB_TYPE, "queued"), 0),
            "running_jobs": sum(count for (job_type, status), count in counts.items() if status == "running"),
        }

    def _worker_status(self, row, job_rows: dict[str, dict[str, Any]], eval_rows: dict[str, dict[str, Any]], online_cutoff) -> dict[str, Any]:
        online = row["last_seen_at"] >= online_cutoff
        status = str(row["status"]) if online else "offline"
        job = self._worker_current_job(row, job_rows, eval_rows)
        return {
            "worker_id": row["worker_id"],
            "status": status,
            "online": online,
            "last_seen_at": row["last_seen_at"],
            "started_at": row["started_at"],
            "current_job": job,
            "metadata": self._worker_metadata(row["metadata"]),
        }

    def _worker_metadata(self, raw_metadata: Any) -> dict[str, Any]:
        if not isinstance(raw_metadata, dict):
            return {}
        return {key: raw_metadata[key] for key in SAFE_WORKER_METADATA_KEYS if key in raw_metadata}

    def _worker_current_job(self, row, job_rows: dict[str, dict[str, Any]], eval_rows: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        job_id = row["current_job_id"]
        if not job_id:
            return None
        job = job_rows.get(job_id, {})
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        run_id = row["current_run_id"] or payload.get("eval_case_run_id")
        session_id = row["current_session_id"] or payload.get("session_id")
        eval_run = eval_rows.get(str(run_id)) if run_id else None
        result: dict[str, Any] = {
            "id": job_id,
            "type": job.get("type") or row["current_job_type"],
            "attempts": job.get("attempts", 0),
            "started_at": job.get("started_at"),
            "run_id": run_id,
            "session_id": session_id,
            "error": job.get("error"),
        }
        if eval_run:
            result["skill_id"] = eval_run.get("skill_id")
            result["skill_version_id"] = eval_run.get("skill_version_id")
        return result
