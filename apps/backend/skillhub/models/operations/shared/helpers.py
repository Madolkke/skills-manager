from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from sqlalchemy import desc, insert, select

from skillhub.models.entities import ContentRef, digest_text, new_id
from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.rules.semver import next_patch_version
from skillhub.models.schema import orm


class CoreHelperMixin:
    def _required_text(item: dict[str, Any], key: str) -> str:
        value = item.get(key)
        return value.strip() if isinstance(value, str) else ""

    def _skill_row(self, connection, skill_id: str):
        row = connection.execute(orm.select_entity(orm.Skill).where(orm.Skill.id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return row

    def _skill_version_row(self, connection, version_id: str):
        row = connection.execute(orm.select_entity(orm.SkillVersion).where(orm.SkillVersion.id == version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"SkillVersion not found: {version_id}")
        return row

    def _eval_case_row(self, connection, case_id: str):
        row = connection.execute(orm.select_entity(orm.EvalCase).where(orm.EvalCase.id == case_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCase not found: {case_id}")
        return row

    def _eval_case_version_row(self, connection, case_version_id: str):
        row = connection.execute(orm.select_entity(orm.EvalCaseVersion).where(orm.EvalCaseVersion.id == case_version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCaseVersion not found: {case_version_id}")
        return row

    def _primary_eval_set_row(self, connection, skill_id: str):
        row = (
            connection.execute(
                orm.select_entity(orm.EvalSet).where(orm.EvalSet.skill_id == skill_id).where(orm.EvalSet.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"Primary EvalSet not found for skill: {skill_id}")
        return row

    def _eval_set_row(self, connection, eval_set_id: str):
        row = connection.execute(orm.select_entity(orm.EvalSet).where(orm.EvalSet.id == eval_set_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalSet not found: {eval_set_id}")
        return row

    def _eval_run_row(self, connection, eval_run_id: str):
        row = connection.execute(orm.select_entity(orm.EvalRun).where(orm.EvalRun.id == eval_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalRun not found: {eval_run_id}")
        return row

    def _eval_case_run_row(self, connection, eval_case_run_id: str):
        row = connection.execute(orm.select_entity(orm.EvalCaseRun).where(orm.EvalCaseRun.id == eval_case_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCaseRun not found: {eval_case_run_id}")
        return row

    def _accepted_verification_row(self, connection, accepted_verification_id: str):
        row = (
            connection.execute(orm.select_entity(orm.AcceptedVerification).where(orm.AcceptedVerification.id == accepted_verification_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"AcceptedVerification not found: {accepted_verification_id}")
        return row

    def _accepted_verification_for_eval_run(self, connection, eval_run_id: str) -> dict[str, Any] | None:
        row = connection.execute(orm.select_entity(orm.AcceptedVerification).where(orm.AcceptedVerification.eval_run_id == eval_run_id)).mappings().one_or_none()
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
                orm.select_entity(orm.AcceptedVerification)
                .where(orm.AcceptedVerification.skill_id == skill_id)
                .where(orm.AcceptedVerification.skill_version_id == skill_version_id)
                .where(orm.AcceptedVerification.eval_set_id == eval_set_id)
                .where(orm.AcceptedVerification.run_context_hash == run_context_hash)
            )
            .mappings()
            .one_or_none()
        )
        return self._row_dict(row) if row is not None else None

    def _next_skill_version_number(self, connection, skill_id: str) -> int:
        return 1 + max(
            connection.execute(select(orm.SkillVersion.version_number).where(orm.SkillVersion.skill_id == skill_id)).scalars(),
            default=0,
        )

    def _next_skill_semver(self, connection, skill_id: str) -> str:
        current = (
            connection.execute(
                select(orm.SkillVersion.version)
                .where(orm.SkillVersion.skill_id == skill_id)
                .order_by(desc(orm.SkillVersion.version_number))
                .limit(1)
            )
            .scalars()
            .one_or_none()
        )
        return next_patch_version(current)

    def _next_eval_case_version_number(self, connection, case_id: str) -> int:
        return 1 + max(
            connection.execute(select(orm.EvalCaseVersion.version_number).where(orm.EvalCaseVersion.case_id == case_id)).scalars(),
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
                select(orm.Artifact.id)
                .where(orm.Artifact.locator == f"inline:{content_digest}")
                .where(orm.Artifact.digest == content_digest)
            )
            .scalars()
            .one_or_none()
        )
        if existing is not None:
            return existing
        artifact_id = new_id("artifact")
        connection.execute(
            insert(orm.Artifact).values(
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
                select(orm.Artifact.id)
                .where(orm.Artifact.locator == locator)
                .where(orm.Artifact.digest == content_digest)
            )
            .scalars()
            .one_or_none()
        )
        if existing is not None:
            return existing
        artifact_id = new_id("artifact")
        connection.execute(
            insert(orm.Artifact).values(
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
        from skillhub.models.rules.eval_runs import canonical_run_context

        return canonical_run_context(value)

    def _run_context_hash(self, tags: tuple[str, ...], context: dict[str, Any]) -> str:
        from skillhub.models.rules.eval_runs import run_context_hash

        return run_context_hash(tags, context)

    def _row_dict(self, row) -> dict[str, Any]:
        return dict(row)


def clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
