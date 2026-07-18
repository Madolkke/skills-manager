from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id
from skillhub.models.schema import orm


class JobHelperMixin:
    def _insert_job(
        self,
        connection,
        *,
        job_type: str,
        payload: dict[str, Any],
        actor: str,
        created_at: datetime,
    ) -> str:
        job_id = new_id("job")
        connection.execute(
            insert(orm.Job).values(
                id=job_id,
                type=job_type,
                status="queued",
                payload=payload,
                result_ref=None,
                attempts=0,
                locked_by=None,
                last_heartbeat_at=None,
                created_at=created_at,
                created_by=actor,
            )
        )
        return job_id

    def _start_job(self, connection, *, job_id: str, started_at: datetime) -> None:
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job_id)
            .values(status="running", started_at=started_at, last_heartbeat_at=started_at)
        )

    def _finish_job(self, connection, *, job_id: str, result_ref: str | None, finished_at: datetime) -> None:
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job_id)
            .values(status="succeeded", result_ref=result_ref, finished_at=finished_at, locked_by=None, error=None)
        )

    def _fail_job(self, connection, *, job_id: str, error: str, finished_at: datetime) -> None:
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job_id)
            .values(status="failed", error=error, finished_at=finished_at, locked_by=None)
        )
