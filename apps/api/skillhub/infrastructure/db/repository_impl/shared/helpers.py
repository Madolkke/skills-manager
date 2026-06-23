from __future__ import annotations

import base64
from datetime import datetime
import json
from typing import Any

from sqlalchemy import delete, desc, insert, select, tuple_, update

from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError, NotFoundError
from skillhub.domain.models import ContentRef, digest_text, new_id
from skillhub.domain.tag_resources import encode_skill_tag_resource_id
from skillhub.domain.semver import next_patch_version
from skillhub.infrastructure.db import tables


class CoreHelperMixin:
    def _required_text(item: dict[str, Any], key: str) -> str:
        value = item.get(key)
        return value.strip() if isinstance(value, str) else ""

    def _skill_row(self, connection, skill_id: str):
        row = connection.execute(select(tables.skills).where(tables.skills.c.id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return row

    def _skill_tags(self, connection, skill_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(
                    tables.skill_tags.c.tag_group_id,
                    tables.tag_groups.c.display_name.label("group_display_name"),
                    tables.skill_tags.c.tag_value,
                    tables.tag_values.c.display_name.label("value_display_name"),
                )
                .join(tables.tag_groups, tables.tag_groups.c.id == tables.skill_tags.c.tag_group_id)
                .join(
                    tables.tag_values,
                    (tables.tag_values.c.tag_group_id == tables.skill_tags.c.tag_group_id)
                    & (tables.tag_values.c.value == tables.skill_tags.c.tag_value),
                )
                .where(tables.skill_tags.c.skill_id == skill_id)
                .order_by(tables.tag_groups.c.sort_order, tables.skill_tags.c.tag_group_id, tables.tag_values.c.sort_order, tables.skill_tags.c.tag_value)
            )
            .mappings()
            .all()
        )
        return [
            {
                "group_id": row["tag_group_id"],
                "group_display_name": row["group_display_name"],
                "value": row["tag_value"],
                "value_display_name": row["value_display_name"],
            }
            for row in rows
        ]

    def _skill_tag_resource_ids(self, connection, skill_id: str) -> list[str]:
        return [encode_skill_tag_resource_id(tag["group_id"], tag["value"]) for tag in self._skill_tags(connection, skill_id)]

    def _clean_skill_tags(self, tags: list[dict[str, Any]] | None) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in tags or []:
            raw_group_id = item.get("group_id", "") if isinstance(item, dict) else getattr(item, "group_id", "")
            raw_value = item.get("value", "") if isinstance(item, dict) else getattr(item, "value", "")
            group_id = str(raw_group_id).strip()
            value = str(raw_value).strip()
            if not group_id or not value:
                raise FieldInvariantError(
                    "Skill tag requires tag group and value.",
                    [FieldError(field="tags", message="Tag 需要选择 Tag Group 和 Tag 值。", code="skill_tag.required")],
                )
            key = (group_id, value)
            if key not in seen:
                result.append({"group_id": group_id, "value": value})
                seen.add(key)
        return result

    def _require_tag_values_exist(self, connection, tags: list[dict[str, str]]) -> None:
        if not tags:
            return
        keys = [(tag["group_id"], tag["value"]) for tag in tags]
        existing = set(
            connection.execute(
                select(tables.tag_values.c.tag_group_id, tables.tag_values.c.value).where(
                    tuple_(tables.tag_values.c.tag_group_id, tables.tag_values.c.value).in_(keys)
                )
            ).all()
        )
        missing = [tag for tag in tags if (tag["group_id"], tag["value"]) not in existing]
        if missing:
            message = "、".join(f"{item['group_id']}:{item['value']}" for item in missing)
            raise FieldInvariantError(
                "Skill tag must exist in a tag group.",
                [FieldError(field="tags", message=f"Tag 必须先在后台 Tag Group 中定义：{message}", code="skill_tag.undefined")],
            )

    def _protected_skill_tags(self, connection, tags: set[tuple[str, str]]) -> set[tuple[str, str]]:
        if not tags:
            return set()
        resource_ids = [encode_skill_tag_resource_id(group_id, value) for group_id, value in tags]
        protected_ids = set(
            connection.execute(
                select(tables.role_assignments.c.resource_id)
                .where(tables.role_assignments.c.resource_type == "skill_tag")
                .where(tables.role_assignments.c.resource_id.in_(resource_ids))
            ).scalars()
        )
        return {tag for tag in tags if encode_skill_tag_resource_id(tag[0], tag[1]) in protected_ids}

    def _set_skill_tags(
        self,
        connection,
        *,
        skill_id: str,
        tags: list[dict[str, Any]],
        actor: str,
        created_at: datetime,
        enforce_protected: bool = True,
    ) -> None:
        clean_tags = self._clean_skill_tags(tags)
        self._require_tag_values_exist(connection, clean_tags)
        current_tags = {
            (tag["group_id"], tag["value"])
            for tag in self._skill_tags(connection, skill_id)
        }
        next_tags = {(tag["group_id"], tag["value"]) for tag in clean_tags}
        changed_tags = current_tags.symmetric_difference(next_tags)
        protected_changes = self._protected_skill_tags(connection, changed_tags)
        if enforce_protected and protected_changes:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="tag.protected.manage")
        connection.execute(delete(tables.skill_tags).where(tables.skill_tags.c.skill_id == skill_id))
        for tag in clean_tags:
            connection.execute(
                insert(tables.skill_tags).values(
                    skill_id=skill_id,
                    tag_group_id=tag["group_id"],
                    tag_value=tag["value"],
                    created_at=created_at,
                    created_by=actor,
                )
            )

    def _require_protected_tag_creation_permission(self, connection, *, tags: list[dict[str, Any]], actor: str) -> None:
        clean_tags = self._clean_skill_tags(tags)
        self._require_tag_values_exist(connection, clean_tags)
        protected_tags = self._protected_skill_tags(connection, {(tag["group_id"], tag["value"]) for tag in clean_tags})
        if not protected_tags:
            return
        allowed_tags = {
            source["resource_id"]
            for source in self._actor_tag_role_sources(connection, actor=actor, tags=protected_tags)
            if source["role"] == "admin"
        }
        missing = {tag for tag in protected_tags if encode_skill_tag_resource_id(tag[0], tag[1]) not in allowed_tags}
        if missing:
            formatted = ", ".join(sorted(f"{group_id}:{value}" for group_id, value in missing))
            raise InvariantError(f"Adding protected Skill tags requires admin role: {formatted}")

    def _skill_version_row(self, connection, version_id: str):
        row = connection.execute(select(tables.skill_versions).where(tables.skill_versions.c.id == version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"SkillVersion not found: {version_id}")
        return row

    def _eval_case_row(self, connection, case_id: str):
        row = connection.execute(select(tables.eval_cases).where(tables.eval_cases.c.id == case_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCase not found: {case_id}")
        return row

    def _eval_case_version_row(self, connection, case_version_id: str):
        row = connection.execute(select(tables.eval_case_versions).where(tables.eval_case_versions.c.id == case_version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCaseVersion not found: {case_version_id}")
        return row

    def _primary_eval_set_row(self, connection, skill_id: str):
        row = (
            connection.execute(
                select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill_id).where(tables.eval_sets.c.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"Primary EvalSet not found for skill: {skill_id}")
        return row

    def _eval_set_row(self, connection, eval_set_id: str):
        row = connection.execute(select(tables.eval_sets).where(tables.eval_sets.c.id == eval_set_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalSet not found: {eval_set_id}")
        return row

    def _eval_run_row(self, connection, eval_run_id: str):
        row = connection.execute(select(tables.eval_runs).where(tables.eval_runs.c.id == eval_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalRun not found: {eval_run_id}")
        return row

    def _eval_case_run_row(self, connection, eval_case_run_id: str):
        row = connection.execute(select(tables.eval_case_runs).where(tables.eval_case_runs.c.id == eval_case_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCaseRun not found: {eval_case_run_id}")
        return row

    def _accepted_verification_row(self, connection, accepted_verification_id: str):
        row = (
            connection.execute(select(tables.accepted_verifications).where(tables.accepted_verifications.c.id == accepted_verification_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"AcceptedVerification not found: {accepted_verification_id}")
        return row

    def _accepted_verification_for_eval_run(self, connection, eval_run_id: str) -> dict[str, Any] | None:
        row = connection.execute(select(tables.accepted_verifications).where(tables.accepted_verifications.c.eval_run_id == eval_run_id)).mappings().one_or_none()
        return self._row_dict(row) if row is not None else None

    def _accepted_verification_for_context(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        eval_set_id: str,
        run_context_hash: str,
    ) -> dict[str, Any] | None:
        row = (
            connection.execute(
                select(tables.accepted_verifications)
                .where(tables.accepted_verifications.c.skill_id == skill_id)
                .where(tables.accepted_verifications.c.skill_version_id == skill_version_id)
                .where(tables.accepted_verifications.c.eval_set_id == eval_set_id)
                .where(tables.accepted_verifications.c.run_context_hash == run_context_hash)
            )
            .mappings()
            .one_or_none()
        )
        return self._row_dict(row) if row is not None else None

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
            insert(tables.jobs).values(
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
            update(tables.jobs)
            .where(tables.jobs.c.id == job_id)
            .values(status="running", started_at=started_at, last_heartbeat_at=started_at)
        )

    def _finish_job(self, connection, *, job_id: str, result_ref: str | None, finished_at: datetime) -> None:
        connection.execute(
            update(tables.jobs)
            .where(tables.jobs.c.id == job_id)
            .values(status="succeeded", result_ref=result_ref, finished_at=finished_at, locked_by=None, error=None)
        )

    def _fail_job(self, connection, *, job_id: str, error: str, finished_at: datetime) -> None:
        connection.execute(
            update(tables.jobs)
            .where(tables.jobs.c.id == job_id)
            .values(status="failed", error=error, finished_at=finished_at, locked_by=None)
        )

    def _next_skill_version_number(self, connection, skill_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.skill_versions.c.version_number).where(tables.skill_versions.c.skill_id == skill_id)).scalars(),
            default=0,
        )

    def _next_skill_semver(self, connection, skill_id: str) -> str:
        current = (
            connection.execute(
                select(tables.skill_versions.c.version)
                .where(tables.skill_versions.c.skill_id == skill_id)
                .order_by(desc(tables.skill_versions.c.version_number))
                .limit(1)
            )
            .scalars()
            .one_or_none()
        )
        return next_patch_version(current)

    def _next_eval_case_version_number(self, connection, case_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.eval_case_versions.c.version_number).where(tables.eval_case_versions.c.case_id == case_id)).scalars(),
            default=0,
        )

    def _insert_text_artifact(
        self,
        connection,
        *,
        kind: str,
        namespace: str,
        content: str,
        actor: str,
        created_at: datetime,
    ) -> str:
        content_digest = digest_text(content)
        existing = (
            connection.execute(
                select(tables.artifacts.c.id)
                .where(tables.artifacts.c.locator == f"inline:{content_digest}")
                .where(tables.artifacts.c.digest == content_digest)
            )
            .scalars()
            .one_or_none()
        )
        if existing is not None:
            return existing
        artifact_id = new_id("artifact")
        connection.execute(
            insert(tables.artifacts).values(
                id=artifact_id,
                kind=kind,
                namespace=namespace,
                locator=f"inline:{content_digest}",
                digest=content_digest,
                media_type="text/plain",
                size_bytes=len(content.encode("utf-8")),
                content_text=content,
                created_at=created_at,
                created_by=actor,
            )
        )
        return artifact_id

    def _insert_zip_artifact(
        self,
        connection,
        *,
        namespace: str,
        filename: str,
        content_base64: str,
        actor: str,
        created_at: datetime,
    ) -> str:
        clean_name = filename.strip() or "workspace.zip"
        if not clean_name.lower().endswith(".zip"):
            raise InvariantError("Eval case workspace must be a zip file.")
        try:
            raw_content = base64.b64decode(content_base64, validate=True)
        except ValueError as exc:
            raise InvariantError("Eval case workspace must be valid base64.") from exc
        if not raw_content.startswith(b"PK"):
            raise InvariantError("Eval case workspace must be a zip file.")
        content_digest = digest_text(content_base64)
        locator = f"case-workspace:{content_digest}:{clean_name}"
        existing = (
            connection.execute(
                select(tables.artifacts.c.id)
                .where(tables.artifacts.c.locator == locator)
                .where(tables.artifacts.c.digest == content_digest)
            )
            .scalars()
            .one_or_none()
        )
        if existing is not None:
            return existing
        artifact_id = new_id("artifact")
        connection.execute(
            insert(tables.artifacts).values(
                id=artifact_id,
                kind="eval_case_workspace",
                namespace=namespace,
                locator=locator,
                digest=content_digest,
                media_type="application/zip",
                size_bytes=len(raw_content),
                content_text=content_base64,
                created_at=created_at,
                created_by=actor,
            )
        )
        return artifact_id

    def _create_case_workspace(
        self,
        connection,
        *,
        skill_id: str,
        actor: str,
        workspace_name: str | None,
        workspace_base64: str | None,
        created_at: datetime,
    ) -> str | None:
        if not workspace_base64:
            return None
        filename = workspace_name or "workspace.zip"
        return self._insert_zip_artifact(
            connection,
            namespace=skill_id,
            filename=filename,
            content_base64=workspace_base64,
            actor=actor,
            created_at=created_at,
        )

    def _content_ref_payload(self, content_ref: ContentRef) -> dict[str, str]:
        payload = {"kind": content_ref.kind, "locator": content_ref.locator, "digest": content_ref.digest}
        if content_ref.path is not None:
            payload["path"] = content_ref.path
        return payload

    def _canonical_json_object(self, value: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        except (TypeError, ValueError) as exc:
            raise InvariantError("Run context must be JSON serializable.") from exc

    def _run_context_hash(self, tags: tuple[str, ...], context: dict[str, Any]) -> str:
        payload = {"environment_tags": list(tags), "run_context": context}
        return digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _row_dict(self, row) -> dict[str, Any]:
        return dict(row)


def clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
