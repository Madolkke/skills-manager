from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import NotFoundError
from skillhub.models.schema import orm

from .constants import BUILDER_JOB_TYPE, BUILDER_RUNNER, clean_builder_progress_stage

logger = logging.getLogger(__name__)


class SkillBuilderJobMixin:
    def claim_next_skill_builder_job(self, *, worker_id: str, runner: str = BUILDER_RUNNER) -> dict[str, Any] | None:
        now = utc_now()
        with self._write_session() as connection:
            job = (
                connection.execute(
                    orm.select_entity(orm.Job)
                    .where(orm.Job.type == BUILDER_JOB_TYPE)
                    .where(orm.Job.status == "queued")
                    .where(orm.Job.payload["runner"].as_string() == runner)
                    .order_by(orm.Job.created_at, orm.Job.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .one_or_none()
            )
            if job is None:
                return None
            payload = dict(job["payload"])
            session_id = str(payload["session_id"])
            message_id = str(payload["message_id"])
            session = (
                connection.execute(
                    orm.select_entity(orm.SkillBuilderSession)
                    .where(orm.SkillBuilderSession.id == session_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if session is None or session["status"] != "running":
                self._cancel_orphaned_builder_job(connection, job=job, now=now, reason="Skill Builder session is not running.")
                return None
            if self._builder_job_is_stale(job, session, now=now):
                self._fail_stale_builder_session(
                    connection,
                    session=session,
                    job=job,
                    now=now,
                    message="AI 创建任务长时间没有进展，已自动释放会话。你可以继续发送消息或新建会话。",
                )
                return None
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job["id"])
                .values(
                    status="running",
                    payload={**payload, "progress_stage": "claimed", "progress_updated_at": now.isoformat()},
                    attempts=job["attempts"] + 1,
                    locked_by=worker_id,
                    started_at=job["started_at"] or now,
                    last_heartbeat_at=now,
                    error=None,
                )
            )
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(status="running", last_error=None, updated_at=now)
            )
        return self.skill_builder_job_detail(session_id=session_id, message_id=message_id, job_id=str(job["id"]))

    def skill_builder_job_detail(self, *, session_id: str, message_id: str, job_id: str) -> dict[str, Any]:
        with self._write_session() as connection:
            session = self._builder_session_row(connection, session_id=session_id, actor=None)
            message = (
                connection.execute(orm.select_entity(orm.SkillBuilderMessage).where(orm.SkillBuilderMessage.id == message_id))
                .mappings()
                .one_or_none()
            )
            job = connection.execute(orm.select_entity(orm.Job).where(orm.Job.id == job_id)).mappings().one_or_none()
            if message is None or job is None:
                raise NotFoundError(f"Skill builder job not found: {job_id}")
            messages = self._builder_messages(connection, session_id=session_id)
        return {
            "session": self._builder_session_payload(session, messages=messages),
            "message": self._row_dict(message),
            "job": self._row_dict(job),
        }

    def complete_skill_builder_job(
        self,
        *,
        session_id: str,
        job_id: str,
        assistant_content: str,
        intent: str | None,
        draft_files: list[dict[str, Any]] | None,
        opencode_session_id: str | None,
        workdir: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        message_intent = intent if intent in {"chat", "generate_draft"} else "chat"
        with self._write_session() as connection:
            session = self._builder_session_row_or_none(connection, session_id=session_id)
            job = self._builder_job_row_or_none(connection, job_id=job_id)
            if not self._builder_job_can_finish(session=session, job=job, session_id=session_id, job_id=job_id):
                return {}
            clean_workspace = self._clean_builder_workspace_files(draft_files or [], require_entry=False) if draft_files is not None else None
            connection.execute(
                insert(orm.SkillBuilderMessage).values(
                    id=new_id("buildermsg"),
                    session_id=session_id,
                    role="assistant",
                    intent=message_intent,
                    content=assistant_content,
                    metadata_payload=self._canonical_json_object(metadata or {}),
                    job_id=job_id,
                    created_at=now,
                )
            )
            values: dict[str, Any] = {
                "status": "draft_ready" if message_intent == "generate_draft" and clean_workspace else "active",
                "last_error": None,
                "updated_at": now,
            }
            if clean_workspace is not None:
                values["draft_files"] = clean_workspace
            if opencode_session_id:
                values["opencode_session_id"] = opencode_session_id
            if workdir:
                values["workdir"] = workdir
            connection.execute(update(orm.SkillBuilderSession).where(orm.SkillBuilderSession.id == session_id).values(**values))
            self._finish_job(connection, job_id=job_id, result_ref=session_id, finished_at=now)
        return {}

    def fail_skill_builder_job(self, *, session_id: str, job_id: str, error: str) -> None:
        now = utc_now()
        message = error.strip() or "Skill 创建 Agent 执行失败。"
        with self._write_session() as connection:
            session = self._builder_session_row_or_none(connection, session_id=session_id)
            job = self._builder_job_row_or_none(connection, job_id=job_id)
            if not self._builder_job_can_finish(session=session, job=job, session_id=session_id, job_id=job_id):
                return
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(status="failed", last_error=message, updated_at=now)
            )
            self._fail_job(connection, job_id=job_id, error=message, finished_at=now)

    def update_skill_builder_job_progress(self, *, session_id: str, job_id: str, stage: str) -> None:
        now = utc_now()
        clean_stage = clean_builder_progress_stage(stage)
        with self._write_session() as connection:
            session = self._builder_session_row_or_none(connection, session_id=session_id)
            job = self._builder_job_row_or_none(connection, job_id=job_id)
            if session is None or job is None or session["status"] != "running" or job["status"] != "running":
                logger.warning(
                    "skill builder progress ignored session_id=%s job_id=%s stage=%s session_status=%s job_status=%s",
                    session_id,
                    job_id,
                    clean_stage,
                    session["status"] if session is not None else "missing",
                    job["status"] if job is not None else "missing",
                )
                return
            payload = dict(job["payload"] or {})
            payload["progress_stage"] = clean_stage
            payload["progress_updated_at"] = now.isoformat()
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == job_id)
                .values(payload=payload, last_heartbeat_at=now)
            )
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(updated_at=now)
            )

    def _builder_session_row_or_none(self, connection, *, session_id: str):
        return (
            connection.execute(
                orm.select_entity(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )

    def _builder_job_row_or_none(self, connection, *, job_id: str):
        return connection.execute(orm.select_entity(orm.Job).where(orm.Job.id == job_id).with_for_update()).mappings().one_or_none()

    def _builder_job_can_finish(self, *, session, job, session_id: str, job_id: str) -> bool:
        if session is not None and job is not None and session["status"] == "running" and job["status"] == "running":
            return True
        logger.warning(
            "late skill builder job result ignored session_id=%s job_id=%s session_status=%s job_status=%s",
            session_id,
            job_id,
            session["status"] if session is not None else "missing",
            job["status"] if job is not None else "missing",
        )
        return False

    def _cancel_orphaned_builder_job(self, connection, *, job, now, reason: str) -> None:
        connection.execute(
            update(orm.Job)
            .where(orm.Job.id == job["id"])
            .where(orm.Job.status == "queued")
            .values(status="canceled", error=reason, finished_at=now, locked_by=None)
        )
        logger.warning("orphaned skill builder job canceled job_id=%s reason=%s", job["id"], reason)
