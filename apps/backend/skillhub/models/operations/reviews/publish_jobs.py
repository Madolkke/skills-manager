from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.schema import orm

PUBLISH_RELEASE_JOB_TYPE = "publish_release"
PUBLISH_RELEASE_PAYLOAD_VERSION = 1


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
            if record["status"] != "pending_confirmation":
                self._finish_job(connection, job_id=job["id"], result_ref=publish_record_id, finished_at=now)
                return None
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job["id"])
                .values(
                    status="running",
                    attempts=job["attempts"] + 1,
                    locked_by=worker_id,
                    started_at=job["started_at"] or now,
                    last_heartbeat_at=now,
                    error=None,
                )
            )
            return {
                "job": {**self._row_dict(job), "status": "running", "locked_by": worker_id},
                "record": self._row_dict(record),
                "release_payload": self._publish_release_payload(connection, record, confirmed_by=worker_id),
            }

    def complete_publish_release_job(
        self,
        *,
        job_id: str,
        publish_record_id: str,
        actor: str,
        release_result: dict[str, Any],
    ) -> dict[str, Any]:
        finished_at = utc_now()
        with self._write_session() as connection:
            job = self._publish_job_row(connection, job_id)
            self._assert_publish_job_matches(job, publish_record_id)
            record = self._publish_record_row(connection, publish_record_id)
            if record["status"] != "pending_confirmation":
                raise InvariantError("Only pending publish records can be completed.")
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(
                    status="released",
                    metadata_payload={"release_result": release_result, "auto_publish": True},
                    confirmed_at=finished_at,
                    confirmed_by=actor,
                )
            )
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="publish.released",
                    resource_type="publish_record",
                    resource_id=publish_record_id,
                    payload={"publish_target_id": record["publish_target_id"], "skill_version_id": record["skill_version_id"]},
                    created_at=finished_at,
                )
            )
            self._finish_job(connection, job_id=job_id, result_ref=publish_record_id, finished_at=finished_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def fail_publish_release_job(self, *, job_id: str, publish_record_id: str, actor: str, error: str) -> dict[str, Any]:
        finished_at = utc_now()
        message = error.strip() or "Publish release failed."
        with self._write_session() as connection:
            job = self._publish_job_row(connection, job_id)
            self._assert_publish_job_matches(job, publish_record_id)
            self._publish_record_row(connection, publish_record_id)
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(
                    status="failed",
                    metadata_payload={"auto_publish": True, "release_error": message},
                    confirmed_at=finished_at,
                    confirmed_by=actor,
                )
            )
            self._fail_job(connection, job_id=job_id, error=message, finished_at=finished_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def _publish_job_row(self, connection, job_id: str):
        row = (
            connection.execute(orm.select_entity(orm.Job).where(orm.Job.id == job_id).with_for_update())
            .mappings()
            .one_or_none()
        )
        if row is None or row["type"] != PUBLISH_RELEASE_JOB_TYPE:
            raise InvariantError("Publish release job not found.")
        return row

    def _assert_publish_job_matches(self, job, publish_record_id: str) -> None:
        payload = dict(job["payload"] or {})
        self._validate_publish_job_payload(payload)
        if payload["publish_record_id"] != publish_record_id or job["status"] != "running":
            raise InvariantError("Publish release job state does not match the record.")

    def _validate_publish_job_payload(self, payload: dict[str, Any]) -> None:
        if payload.get("schema_version") != PUBLISH_RELEASE_PAYLOAD_VERSION or not payload.get("publish_record_id"):
            raise InvariantError("Publish release job payload is invalid.")
