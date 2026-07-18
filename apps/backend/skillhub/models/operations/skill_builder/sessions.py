from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import ContentRef, new_id, utc_now
from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.rules.skills import initial_skill_version
from skillhub.models.schema import orm

from .constants import BUILDER_JOB_TYPE, BUILDER_RUNNER


class SkillBuilderSessionMixin:
    def list_skill_builder_sessions(self, *, actor: str) -> list[dict[str, Any]]:
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, now=utc_now())
            rows = (
                connection.execute(
                    orm.select_entity(orm.SkillBuilderSession)
                    .where(orm.SkillBuilderSession.actor_ref == actor)
                    .order_by(orm.SkillBuilderSession.updated_at.desc(), orm.SkillBuilderSession.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .all()
            )
            payloads = [self._builder_session_payload_with_progress(connection, row, messages=[]) for row in rows]
        return payloads

    def create_skill_builder_session(self, *, actor: str, title: str | None = None, replace_running: bool = False) -> dict[str, Any]:
        now = utc_now()
        session_id = new_id("builder")
        clean_title = (title or "").strip()[:160]
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, now=now)
            existing = (
                connection.execute(
                    orm.select_entity(orm.SkillBuilderSession)
                    .where(orm.SkillBuilderSession.actor_ref == actor)
                    .with_for_update()
                )
                .mappings()
                .all()
            )
            running_session_ids = [str(row["id"]) for row in existing if row["status"] == "running"]
            if running_session_ids and not replace_running:
                raise ConflictError("Skill 创建 Agent 正在运行，完成后才能新建会话。")
            if replace_running:
                for old_session_id in running_session_ids:
                    self._cancel_builder_session_job(
                        connection,
                        session_id=old_session_id,
                        now=now,
                        message="Skill Builder session was replaced by a new session.",
                    )
            self._delete_existing_skill_builder_sessions(
                connection,
                actor=actor,
                session_ids=[str(row["id"]) for row in existing],
                now=now,
            )
            connection.execute(
                insert(orm.SkillBuilderSession).values(
                    id=session_id,
                    actor_ref=actor,
                    title=clean_title,
                    status="active",
                    opencode_session_id=None,
                    workdir=None,
                    draft_files=[],
                    run_selection={},
                    created_skill_id=None,
                    created_skill_version_id=None,
                    last_error=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = self._builder_session_row(connection, session_id=session_id, actor=actor)
        return self._builder_session_payload(row, messages=[])

    def skill_builder_session_detail(self, *, session_id: str, actor: str) -> dict[str, Any]:
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, session_id=session_id, now=utc_now())
            row = self._builder_session_row(connection, session_id=session_id, actor=actor)
            messages = self._builder_messages(connection, session_id=session_id)
            payload = self._builder_session_payload_with_progress(connection, row, messages=messages)
        return payload

    def enqueue_skill_builder_message(
        self,
        *,
        session_id: str,
        actor: str,
        content: str,
        intent: str,
        run_selection: dict[str, Any],
    ) -> dict[str, Any]:
        clean_content = content.strip()
        if not clean_content:
            raise FieldInvariantError(
                "Skill builder message cannot be empty.",
                [FieldError(field="content", message="请输入要发送给 Skill 创建 Agent 的内容。", code="skill_builder.content_required")],
            )
        if intent not in {"chat", "generate_draft"}:
            raise InvariantError("Skill builder message intent is invalid.")
        clean_selection = self._clean_builder_run_selection(run_selection)
        now = utc_now()
        message_id = new_id("buildermsg")
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, session_id=session_id, now=now)
            session = self._builder_session_row(connection, session_id=session_id, actor=actor)
            if session["status"] == "running":
                raise ConflictError("Skill 创建 Agent 正在处理上一条消息，请稍后。")
            if session["status"] == "created":
                raise InvariantError("该创建会话已经完成，不能继续发送消息。")
            connection.execute(
                insert(orm.SkillBuilderMessage).values(
                    id=message_id,
                    session_id=session_id,
                    role="user",
                    intent=intent,
                    content=clean_content,
                    metadata_payload={"run_selection": clean_selection},
                    job_id=None,
                    created_at=now,
                )
            )
            job_id = self._insert_job(
                connection,
                job_type=BUILDER_JOB_TYPE,
                payload={
                    "runner": BUILDER_RUNNER,
                    "session_id": session_id,
                    "message_id": message_id,
                    "intent": intent,
                    "provider_id": clean_selection.get("provider_id", ""),
                    "model_id": clean_selection.get("model_id", ""),
                    "progress_stage": "queued",
                    "progress_updated_at": now.isoformat(),
                },
                actor=actor,
                created_at=now,
            )
            connection.execute(
                update(orm.SkillBuilderMessage)
                .where(orm.SkillBuilderMessage.id == message_id)
                .values(job_id=job_id)
            )
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(status="running", run_selection=clean_selection, last_error=None, updated_at=now)
            )
        return self.skill_builder_session_detail(session_id=session_id, actor=actor)

    def update_skill_builder_workspace(self, *, session_id: str, actor: str, files: list[dict[str, Any]]) -> dict[str, Any]:
        workspace_files = self._clean_builder_workspace_files(files, require_entry=False)
        now = utc_now()
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, session_id=session_id, now=now)
            session = self._builder_session_row(connection, session_id=session_id, actor=actor)
            if session["status"] == "running":
                raise ConflictError("Skill 创建 Agent 正在处理消息，暂不能编辑工作区文件。")
            if session["status"] == "created":
                raise InvariantError("该创建会话已经完成，不能继续编辑工作区文件。")
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(status="active", draft_files=workspace_files, last_error=None, updated_at=now)
            )
        return self.skill_builder_session_detail(session_id=session_id, actor=actor)

    def update_skill_builder_draft(self, *, session_id: str, actor: str, files: list[dict[str, Any]]) -> dict[str, Any]:
        return self.update_skill_builder_workspace(session_id=session_id, actor=actor, files=files)

    def create_skill_from_builder_session(
        self,
        *,
        session_id: str,
        actor: str,
        version: str | None,
        tags: list[dict[str, Any]],
        files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._write_session() as connection:
            self._recover_stale_builder_sessions(connection, actor=actor, session_id=session_id, now=now)
            session = self._builder_session_row(connection, session_id=session_id, actor=actor)
            if session["status"] == "running":
                raise ConflictError("Skill 创建 Agent 正在处理消息，暂不能创建 Skill。")
            if session["status"] == "created":
                raise InvariantError("该创建会话已经创建过 Skill。")
            bundle_files = self._clean_builder_workspace_files(
                list(session["draft_files"] or []) if files is None else files,
                require_entry=True,
            )
            bundle = parse_skill_import_source({"kind": "files", "name": "builder-workspace", "files": bundle_files})
            artifact_id = self._insert_text_artifact(
                connection,
                kind="skill_bundle",
                namespace=f"skill-builder:{session_id}:{bundle.slug}",
                content=bundle.manifest_text,
                actor=actor,
                created_at=now,
            )
            result = self.insert_skill_with_initial_version(
                slug=bundle.slug,
                owner_ref=actor,
                content_ref=ContentRef(kind="artifact", locator=f"artifact:{artifact_id}", digest=bundle.digest, path=bundle.entry_path),
                change_summary=f"Created by Skill Builder session {session_id}.",
                version=initial_skill_version(version),
                tags=tags,
                actor=actor,
                creator_role_reason="skill.builder",
                connection=connection,
            )
            connection.execute(
                update(orm.SkillBuilderSession)
                .where(orm.SkillBuilderSession.id == session_id)
                .values(
                    status="created",
                    created_skill_id=result.skill_id,
                    created_skill_version_id=result.skill_version_id,
                    last_error=None,
                    updated_at=now,
                )
            )
        return {
            "skill_id": result.skill_id,
            "skill_version_id": result.skill_version_id,
            "slug": bundle.slug,
            "description": bundle.description,
            "file_count": bundle.file_count,
            "entry_path": bundle.entry_path,
            "bundle_artifact_id": artifact_id,
            "bundle_digest": bundle.digest,
        }
