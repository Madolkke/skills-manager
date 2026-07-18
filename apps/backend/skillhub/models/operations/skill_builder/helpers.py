from __future__ import annotations

from typing import Any

from sqlalchemy import delete, update

from skillhub.models.errors import FieldError, FieldInvariantError, NotFoundError
from skillhub.models.schema import orm

from .constants import BUILDER_JOB_TYPE


class SkillBuilderHelperMixin:
    def _builder_session_row(self, connection, *, session_id: str, actor: str | None):
        query = orm.select_entity(orm.SkillBuilderSession).where(orm.SkillBuilderSession.id == session_id)
        if actor is not None:
            query = query.where(orm.SkillBuilderSession.actor_ref == actor)
        row = connection.execute(query).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"SkillBuilderSession not found: {session_id}")
        return row

    def _builder_messages(self, connection, *, session_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                orm.select_entity(orm.SkillBuilderMessage)
                .where(orm.SkillBuilderMessage.session_id == session_id)
                .order_by(orm.SkillBuilderMessage.created_at, orm.SkillBuilderMessage.id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _delete_existing_skill_builder_sessions(self, connection, *, actor: str, session_ids: list[str], now) -> None:
        if not session_ids:
            return
        connection.execute(
            update(orm.Job)
            .where(orm.Job.type == BUILDER_JOB_TYPE)
            .where(orm.Job.status.in_(["queued", "running"]))
            .where(orm.Job.payload["session_id"].as_string().in_(session_ids))
            .values(
                status="canceled",
                error="Skill Builder session was replaced by a new session.",
                finished_at=now,
                locked_by=None,
            )
        )
        connection.execute(delete(orm.SkillBuilderMessage).where(orm.SkillBuilderMessage.session_id.in_(session_ids)))
        connection.execute(
            delete(orm.SkillBuilderSession)
            .where(orm.SkillBuilderSession.actor_ref == actor)
            .where(orm.SkillBuilderSession.id.in_(session_ids))
        )

    def _builder_session_payload(self, row, *, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self._row_dict(row)
        payload["draft_files"] = list(payload.get("draft_files") or [])
        payload["workspace_files"] = list(payload["draft_files"])
        payload["run_selection"] = dict(payload.get("run_selection") or {})
        payload["messages"] = messages
        payload["run_progress"] = None
        return payload

    def _builder_session_payload_with_progress(self, connection, row, *, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self._builder_session_payload(row, messages=messages)
        payload["run_progress"] = self._builder_run_progress(connection, session_id=str(row["id"])) if row["status"] == "running" else None
        return payload

    def _builder_run_progress(self, connection, *, session_id: str) -> dict[str, Any] | None:
        row = (
            connection.execute(
                orm.select_entity(orm.Job)
                .join(orm.SkillBuilderMessage, orm.SkillBuilderMessage.job_id == orm.Job.id)
                .where(orm.SkillBuilderMessage.session_id == session_id)
                .where(orm.Job.type == BUILDER_JOB_TYPE)
                .where(orm.Job.status.in_(["queued", "running"]))
                .order_by(orm.Job.created_at.desc(), orm.SkillBuilderMessage.created_at.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        payload = row["payload"] if isinstance(row["payload"], dict) else {}
        return {
            "job_id": row["id"],
            "status": row["status"],
            "stage": str(payload.get("progress_stage") or ("queued" if row["status"] == "queued" else "claimed")),
            "started_at": row["started_at"] or row["created_at"],
            "updated_at": payload.get("progress_updated_at") or row["last_heartbeat_at"] or row["created_at"],
            "attempts": row["attempts"],
        }

    def _clean_builder_run_selection(self, value: dict[str, Any]) -> dict[str, str]:
        provider_id = str(value.get("provider_id") or "").strip()
        model_id = str(value.get("model_id") or "").strip()
        if bool(provider_id) != bool(model_id):
            raise FieldInvariantError(
                "Provider and model must be selected together.",
                [FieldError(field="model_id", message="Provider 和 Model 需要同时选择。", code="skill_builder.model_pair_required")],
            )
        result: dict[str, str] = {}
        if provider_id and model_id:
            result["provider_id"] = provider_id
            result["model_id"] = model_id
        return result

    def _clean_builder_workspace_files(self, files: list[dict[str, Any]], *, require_entry: bool) -> list[dict[str, str]]:
        if not files and require_entry:
            raise FieldInvariantError(
                "Skill builder workspace needs files.",
                [FieldError(field="files", message="提交 Skill 至少需要包含 SKILL.md。", code="skill_builder.files_required")],
            )
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in files:
            path = str(item.get("path") or "").strip()
            content = item.get("content_text")
            if not isinstance(content, str):
                raise FieldInvariantError(
                    "Skill builder workspace files must be text.",
                    [FieldError(field="files", message="工作区文件只能是 UTF-8 文本。", code="skill_builder.text_only")],
                )
            self._validate_builder_draft_path(path)
            if path in seen:
                raise FieldInvariantError(
                    "Skill builder workspace paths must be unique.",
                    [FieldError(field="files", message=f"工作区文件路径重复：{path}", code="skill_builder.duplicate_path")],
                )
            seen.add(path)
            result.append({"path": path, "content_text": content})
        if require_entry and not any(file["path"] == "SKILL.md" for file in result):
            raise FieldInvariantError(
                "Skill builder workspace needs SKILL.md.",
                [FieldError(field="files", message="提交 Skill 必须包含根目录 SKILL.md。", code="skill_builder.entry_required")],
            )
        return result

    def _clean_builder_draft_files(self, files: list[dict[str, Any]]) -> list[dict[str, str]]:
        return self._clean_builder_workspace_files(files, require_entry=True)

    def _validate_builder_draft_path(self, path: str) -> None:
        if not path:
            raise FieldInvariantError(
                "Skill builder workspace path is required.",
                [FieldError(field="files", message="工作区文件路径不能为空。", code="skill_builder.path_required")],
            )
        if "\\" in path or "\x00" in path or path.startswith("/") or path.startswith(".opencode/"):
            raise FieldInvariantError(
                "Skill builder workspace path is unsafe.",
                [FieldError(field="files", message=f"工作区文件路径不安全：{path}", code="skill_builder.unsafe_path")],
            )
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise FieldInvariantError(
                "Skill builder workspace path is unsafe.",
                [FieldError(field="files", message=f"工作区文件路径不能包含空目录、. 或 ..：{path}", code="skill_builder.unsafe_path")],
            )
