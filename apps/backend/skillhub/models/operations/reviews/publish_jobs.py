from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.schema import orm

PUBLISH_RELEASE_JOB_TYPE = "publish_release"
PUBLISH_RELEASE_PAYLOAD_VERSION = 1
logger = logging.getLogger(__name__)


class PublishReleaseJobMixin:
    def _enqueue_publish_release_job(self, connection, *, publish_record_id: str, actor: str, created_at) -> str:
        existing = connection.execute(
            select(orm.Job.id)
            .where(orm.Job.type == PUBLISH_RELEASE_JOB_TYPE)
            .where(orm.Job.status.in_(["queued", "running"]))
            .where(orm.Job.payload["publish_record_id"].as_string() == publish_record_id)
        ).scalar_one_or_none()
        if existing is not None:
            return str(existing)
        return self._insert_job(
            connection,
            job_type=PUBLISH_RELEASE_JOB_TYPE,
            payload={
                "schema_version": PUBLISH_RELEASE_PAYLOAD_VERSION,
                "publish_record_id": publish_record_id,
                "idempotency_key": f"publish_release:{publish_record_id}",
            },
            actor=actor,
            created_at=created_at,
        )

    def _queue_publish_record(self, connection, *, record, actor: str, queued_at) -> str:
        if record["status"] not in {"pending_confirmation", "failed"}:
            raise InvariantError("Only pending or failed publish records can be queued.")
        metadata = dict(record["metadata"] or {})
        metadata.pop("release_error", None)
        metadata.pop("lease_expired", None)
        if actor == "system:auto_publish":
            metadata["auto_publish"] = True
        connection.execute(
            update(orm.PublishRecord)
            .where(orm.PublishRecord.id == record["id"])
            .values(
                status="queued",
                metadata_payload=metadata,
                confirmed_at=queued_at,
                confirmed_by=actor,
            )
        )
        return self._enqueue_publish_release_job(
            connection,
            publish_record_id=str(record["id"]),
            actor=actor,
            created_at=queued_at,
        )

    def claim_next_publish_release_job(self, *, worker_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with self._write_session() as connection:
            job = (
                connection.execute(
                    orm.select_entity(orm.Job)
                    .where(orm.Job.type == PUBLISH_RELEASE_JOB_TYPE)
                    .where(orm.Job.status == "queued")
                    .order_by(orm.Job.created_at, orm.Job.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .one_or_none()
            )
            if job is None:
                return None
            payload = dict(job["payload"] or {})
            self._validate_publish_job_payload(payload)
            publish_record_id = str(payload["publish_record_id"])
            record = self._publish_record_row(connection, publish_record_id)
            if record["status"] != "queued":
                self._fail_job(connection, job_id=job["id"], error="Publish record is not queued.", finished_at=now)
                return None
            attempt = int(job["attempts"]) + 1
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job["id"])
                .values(
                    status="running",
                    attempts=attempt,
                    locked_by=worker_id,
                    started_at=job["started_at"] or now,
                    last_heartbeat_at=now,
                    error=None,
                )
            )
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(status="releasing")
            )
            return {
                "job": {**self._row_dict(job), "status": "running", "locked_by": worker_id, "attempts": attempt},
                "record": {**self._row_dict(record), "status": "releasing"},
                "execution": {"job_id": str(job["id"]), "worker_id": worker_id, "attempt": attempt},
                "release_payload": self._publish_release_payload(connection, record, confirmed_by=worker_id),
            }

    def complete_publish_release_job(
        self,
        *,
        job_id: str,
        publish_record_id: str,
        worker_id: str,
        attempt: int,
        release_result: dict[str, Any],
    ) -> dict[str, Any]:
        finished_at = utc_now()
        with self._write_session() as connection:
            if not self._owned_publish_job(connection, job_id, publish_record_id, worker_id, attempt):
                return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))
            record = self._publish_record_row(connection, publish_record_id)
            if record["status"] != "releasing":
                logger.warning("job.late_result_ignored job_id=%s publish_record_id=%s", job_id, publish_record_id)
                return self._publish_record_detail(connection, record)
            metadata = dict(record["metadata"] or {})
            metadata.update({"release_result": release_result})
            metadata.pop("external_state", None)
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(status="released", metadata_payload=metadata, confirmed_at=finished_at, confirmed_by=worker_id)
            )
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=worker_id,
                    action="publish.released",
                    resource_type="publish_record",
                    resource_id=publish_record_id,
                    payload={"publish_target_id": record["publish_target_id"], "skill_version_id": record["skill_version_id"]},
                    created_at=finished_at,
                )
            )
            self._finish_job(connection, job_id=job_id, result_ref=publish_record_id, finished_at=finished_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def fail_publish_release_job(
        self,
        *,
        job_id: str,
        publish_record_id: str,
        worker_id: str,
        attempt: int,
        error: str,
    ) -> dict[str, Any]:
        finished_at = utc_now()
        message = error.strip() or "Publish release failed."
        with self._write_session() as connection:
            if not self._owned_publish_job(connection, job_id, publish_record_id, worker_id, attempt):
                return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))
            record = self._publish_record_row(connection, publish_record_id)
            metadata = dict(record["metadata"] or {})
            metadata["release_error"] = message
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(status="failed", metadata_payload=metadata, confirmed_at=finished_at, confirmed_by=worker_id)
            )
            self._fail_job(connection, job_id=job_id, error=message, finished_at=finished_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def _owned_publish_job(self, connection, job_id: str, record_id: str, worker_id: str, attempt: int) -> bool:
        job = self._lock_owned_job(connection, job_id=job_id, worker_id=worker_id, attempt=attempt)
        if job is None:
            return False
        payload = dict(job["payload"] or {})
        self._validate_publish_job_payload(payload)
        matches = str(payload["publish_record_id"]) == record_id
        if not matches:
            logger.warning("job.late_result_ignored job_id=%s publish_record_id=%s", job_id, record_id)
        return matches

    def _validate_publish_job_payload(self, payload: dict[str, Any]) -> None:
        if payload.get("schema_version") != PUBLISH_RELEASE_PAYLOAD_VERSION or not payload.get("publish_record_id"):
            raise InvariantError("Publish release job payload is invalid.")
