from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import NotFoundError
from skillhub.models.schema import tables

from .constants import BUILDER_JOB_TYPE, BUILDER_RUNNER


class SkillBuilderJobMixin:
    def claim_next_skill_builder_job(self, *, worker_id: str, runner: str = BUILDER_RUNNER) -> dict[str, Any] | None:
        now = utc_now()
        with self.engine.begin() as connection:
            job = (
                connection.execute(
                    select(tables.jobs)
                    .where(tables.jobs.c.type == BUILDER_JOB_TYPE)
                    .where(tables.jobs.c.status == "queued")
                    .where(tables.jobs.c.payload["runner"].as_string() == runner)
                    .order_by(tables.jobs.c.created_at, tables.jobs.c.id)
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
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job["id"])
                .values(
                    status="running",
                    attempts=job["attempts"] + 1,
                    locked_by=worker_id,
                    started_at=job["started_at"] or now,
                    last_heartbeat_at=now,
                    error=None,
                )
            )
            connection.execute(
                update(tables.skill_builder_sessions)
                .where(tables.skill_builder_sessions.c.id == session_id)
                .values(status="running", last_error=None, updated_at=now)
            )
        return self.skill_builder_job_detail(session_id=session_id, message_id=message_id, job_id=str(job["id"]))

    def skill_builder_job_detail(self, *, session_id: str, message_id: str, job_id: str) -> dict[str, Any]:
        with self.engine.begin() as connection:
            session = self._builder_session_row(connection, session_id=session_id, actor=None)
            message = (
                connection.execute(select(tables.skill_builder_messages).where(tables.skill_builder_messages.c.id == message_id))
                .mappings()
                .one_or_none()
            )
            job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == job_id)).mappings().one_or_none()
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
        clean_workspace = self._clean_builder_workspace_files(draft_files or [], require_entry=False) if draft_files is not None else None
        message_intent = intent if intent in {"chat", "generate_draft"} else "chat"
        with self.engine.begin() as connection:
            self._builder_session_row(connection, session_id=session_id, actor=None)
            connection.execute(
                insert(tables.skill_builder_messages).values(
                    id=new_id("buildermsg"),
                    session_id=session_id,
                    role="assistant",
                    intent=message_intent,
                    content=assistant_content,
                    metadata=self._canonical_json_object(metadata or {}),
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
            connection.execute(update(tables.skill_builder_sessions).where(tables.skill_builder_sessions.c.id == session_id).values(**values))
            self._finish_job(connection, job_id=job_id, result_ref=session_id, finished_at=now)
        return {}

    def fail_skill_builder_job(self, *, session_id: str, job_id: str, error: str) -> None:
        now = utc_now()
        message = error.strip() or "Skill 创建 Agent 执行失败。"
        with self.engine.begin() as connection:
            self._builder_session_row(connection, session_id=session_id, actor=None)
            connection.execute(
                update(tables.skill_builder_sessions)
                .where(tables.skill_builder_sessions.c.id == session_id)
                .values(status="failed", last_error=message, updated_at=now)
            )
            self._fail_job(connection, job_id=job_id, error=message, finished_at=now)
