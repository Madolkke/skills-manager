from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update

from skillhub.models.entities import utc_now
from skillhub.models.schema import tables

from .constants import BUILDER_JOB_TYPE, builder_stale_after_seconds


logger = logging.getLogger(__name__)


class SkillBuilderRecoveryMixin:
    def cancel_skill_builder_session(self, *, session_id: str, actor: str) -> dict[str, Any]:
        now = utc_now()
        with self.engine.begin() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, session_id=session_id, now=now)
            session = self._builder_session_row(connection, session_id=session_id, actor=actor)
            if session["status"] != "running":
                return self._builder_session_payload_with_progress(connection, session, messages=self._builder_messages(connection, session_id=session_id))
            self._cancel_builder_session_job(
                connection,
                session_id=session_id,
                now=now,
                message="本次 AI 创建运行已取消，可继续发送新消息。",
            )
            row = self._builder_session_row(connection, session_id=session_id, actor=actor)
            messages = self._builder_messages(connection, session_id=session_id)
            payload = self._builder_session_payload_with_progress(connection, row, messages=messages)
        return payload

    def _recover_stale_builder_sessions(self, connection, *, actor: str, now, session_id: str | None = None) -> None:
        query = (
            select(tables.skill_builder_sessions)
            .where(tables.skill_builder_sessions.c.actor_ref == actor)
            .where(tables.skill_builder_sessions.c.status == "running")
        )
        if session_id is not None:
            query = query.where(tables.skill_builder_sessions.c.id == session_id)
        rows = connection.execute(query.with_for_update()).mappings().all()
        for session in rows:
            job = self._builder_session_active_job(connection, session_id=str(session["id"]))
            if job is None:
                self._fail_stale_builder_session(
                    connection,
                    session=session,
                    job=None,
                    now=now,
                    message="AI 创建任务已失去运行记录，已自动释放会话。你可以继续发送消息或新建会话。",
                )
                continue
            if self._builder_job_is_stale(job, session, now=now):
                self._fail_stale_builder_session(
                    connection,
                    session=session,
                    job=job,
                    now=now,
                    message="AI 创建任务长时间没有进展，已自动释放会话。你可以继续发送消息或新建会话。",
                )

    def _builder_session_active_job(self, connection, *, session_id: str):
        return (
            connection.execute(
                select(tables.jobs)
                .join(tables.skill_builder_messages, tables.skill_builder_messages.c.job_id == tables.jobs.c.id)
                .where(tables.skill_builder_messages.c.session_id == session_id)
                .where(tables.jobs.c.type == BUILDER_JOB_TYPE)
                .where(tables.jobs.c.status.in_(["queued", "running"]))
                .order_by(tables.jobs.c.created_at.desc(), tables.skill_builder_messages.c.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )

    def _builder_job_is_stale(self, job, session, *, now) -> bool:
        stale_after = timedelta(seconds=builder_stale_after_seconds())
        reference = job["last_heartbeat_at"] or job["started_at"] or job["created_at"] or session["updated_at"]
        return reference is not None and reference <= now - stale_after

    def _fail_stale_builder_session(self, connection, *, session, job, now, message: str) -> None:
        session_id = str(session["id"])
        if job is not None:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job["id"])
                .where(tables.jobs.c.status.in_(["queued", "running"]))
                .values(status="failed", error=message, finished_at=now, locked_by=None)
            )
            logger.warning("stale skill builder job failed session_id=%s job_id=%s", session_id, job["id"])
        connection.execute(
            update(tables.skill_builder_sessions)
            .where(tables.skill_builder_sessions.c.id == session_id)
            .where(tables.skill_builder_sessions.c.status == "running")
            .values(status="failed", last_error=message, updated_at=now)
        )

    def _cancel_builder_session_job(self, connection, *, session_id: str, now, message: str) -> None:
        job = self._builder_session_active_job(connection, session_id=session_id)
        if job is not None:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job["id"])
                .where(tables.jobs.c.status.in_(["queued", "running"]))
                .values(status="canceled", error=message, finished_at=now, locked_by=None)
            )
            logger.info("skill builder job canceled session_id=%s job_id=%s", session_id, job["id"])
        connection.execute(
            update(tables.skill_builder_sessions)
            .where(tables.skill_builder_sessions.c.id == session_id)
            .where(tables.skill_builder_sessions.c.status != "created")
            .values(status="failed", last_error=message, updated_at=now)
        )
