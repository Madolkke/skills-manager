from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import digest_text, new_id, utc_now
from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, NotFoundError
from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class WorkflowSyncCommandMixin(WorkflowHelperMixin):
    def sync_workflow(
        self,
        *,
        skill_id: str,
        version: str,
        display_name: str | None,
        change_summary: str,
        manifest_text: str,
        source_text: str,
        expected_workflow_revision: int,
        expected_document_digest: str,
        generator_id: str,
        generator_version: str,
        generator_options: dict[str, Any],
        generator_options_digest: str,
        preview_digest: str,
        actor: str,
    ) -> dict[str, Any]:
        created_at = utc_now()
        manifest_digest = digest_text(manifest_text)
        try:
            with self._write_session() as connection:
                self._skill_row(connection, skill_id)
                self._require_skill_permission(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    permission="skill.version.create",
                )
                workflow = self._locked_workflow_row(connection, skill_id=skill_id)
                self._assert_preview_is_current(
                    workflow,
                    expected_workflow_revision=expected_workflow_revision,
                    expected_document_digest=expected_document_digest,
                )
                skill = self._skill_row(connection, skill_id)
                existing = self._exact_sync(
                    connection,
                    workflow_id=str(workflow["id"]),
                    workflow_revision=int(workflow["revision"]),
                    generator_id=generator_id,
                    generator_version=generator_version,
                    generator_options_digest=generator_options_digest,
                )
                if existing is not None:
                    existing_version = self._skill_version_row(connection, existing["skill_version_id"])
                    if existing_version["content_digest"] != manifest_digest:
                        raise ConflictError(
                            "Generator 输出已与现有同步证据不一致，请升级 Generator 版本后重新预览。"
                        )
                    return self._reuse_sync(
                        connection,
                        skill=skill,
                        workflow=workflow,
                        sync=existing,
                        actor=actor,
                        updated_at=created_at,
                    )

                semver = normalize_semver(version)
                source_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="workflow_source",
                    namespace=f"workflow:{workflow['id']}:{workflow['revision']}",
                    content=source_text,
                    actor=actor,
                    created_at=created_at,
                )
                bundle_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="skill_bundle",
                    namespace=f"workflow-sync:{skill_id}:{workflow['revision']}:{generator_id}",
                    content=manifest_text,
                    actor=actor,
                    created_at=created_at,
                )
                skill_version_id = new_id("skillver")
                version_number = self._next_skill_version_number(connection, skill_id)
                connection.execute(
                    insert(orm.SkillVersion).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=display_name.strip() if display_name and display_name.strip() else None,
                        content_ref={
                            "kind": "artifact",
                            "locator": f"artifact:{bundle_artifact_id}",
                            "digest": manifest_digest,
                            "path": "SKILL.md",
                        },
                        content_digest=manifest_digest,
                        change_summary=change_summary.strip(),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    insert(orm.WorkflowSync).values(
                        id=new_id("workflowsync"),
                        workflow_id=workflow["id"],
                        workflow_revision=workflow["revision"],
                        document_schema_version=workflow["document_schema_version"],
                        source_artifact_id=source_artifact_id,
                        skill_version_id=skill_version_id,
                        generator_id=generator_id,
                        generator_version=generator_version,
                        generator_options=dict(generator_options),
                        generator_options_digest=generator_options_digest,
                        preview_digest=preview_digest,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(orm.Skill)
                    .where(orm.Skill.id == skill_id)
                    .values(current_version_id=skill_version_id, updated_at=created_at)
                )
                evidence = self._generator_evidence(
                    generator_id=generator_id,
                    generator_version=generator_version,
                    generator_options=generator_options,
                    generator_options_digest=generator_options_digest,
                    preview_digest=preview_digest,
                )
                self._audit_workflow(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    action="workflow.synced",
                    payload={
                        "workflow_id": workflow["id"],
                        "revision": workflow["revision"],
                        "skill_version_id": skill_version_id,
                        **evidence,
                    },
                    created_at=created_at,
                )
        except IntegrityError as exc:
            raise FieldInvariantError(
                "Workflow sync version conflicts with an existing SkillVersion.",
                [
                    FieldError(
                        field="version",
                        message="这个 Skill 已经存在相同版本号。",
                        code="skill_version.version_conflict",
                    )
                ],
            ) from exc
        logger.info(
            "workflow synced skill_id=%s workflow_id=%s revision=%s generator_id=%s generator_version=%s actor=%s",
            skill_id,
            workflow["id"],
            workflow["revision"],
            generator_id,
            generator_version,
            actor,
        )
        return {
            "mode": "created",
            "skill_id": skill_id,
            "skill_version_id": skill_version_id,
            "workflow_revision": workflow["revision"],
            "version": semver,
            "version_number": version_number,
            **evidence,
        }

    def _locked_workflow_row(self, connection, *, skill_id: str):
        workflow = (
            connection.execute(
                orm.select_entity(orm.Workflow)
                .where(orm.Workflow.skill_id == skill_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if workflow is None:
            raise NotFoundError(f"Workflow not found for skill: {skill_id}")
        return workflow

    def _assert_preview_is_current(
        self,
        workflow,
        *,
        expected_workflow_revision: int,
        expected_document_digest: str,
    ) -> None:
        if (
            int(workflow["revision"]) != expected_workflow_revision
            or str(workflow["document_digest"]) != expected_document_digest
        ):
            raise ConflictError("Workflow 已在预览后发生变化，请重新生成预览并确认。")

    def _exact_sync(
        self,
        connection,
        *,
        workflow_id: str,
        workflow_revision: int,
        generator_id: str,
        generator_version: str,
        generator_options_digest: str,
    ):
        return (
            connection.execute(
                orm.select_entity(orm.WorkflowSync)
                .where(orm.WorkflowSync.workflow_id == workflow_id)
                .where(orm.WorkflowSync.workflow_revision == workflow_revision)
                .where(orm.WorkflowSync.generator_id == generator_id)
                .where(orm.WorkflowSync.generator_version == generator_version)
                .where(orm.WorkflowSync.generator_options_digest == generator_options_digest)
            )
            .mappings()
            .one_or_none()
        )

    def _reuse_sync(self, connection, *, skill, workflow, sync, actor: str, updated_at) -> dict[str, Any]:
        current = skill["current_version_id"] == sync["skill_version_id"]
        mode = "already_current" if current else "reactivated"
        evidence = self._generator_evidence_from_sync(sync)
        if not current:
            connection.execute(
                update(orm.Skill)
                .where(orm.Skill.id == skill["id"])
                .values(current_version_id=sync["skill_version_id"], updated_at=updated_at)
            )
            self._audit_workflow(
                connection,
                skill_id=skill["id"],
                actor=actor,
                action="workflow.sync_reactivated",
                payload={
                    "workflow_id": workflow["id"],
                    "revision": workflow["revision"],
                    "skill_version_id": sync["skill_version_id"],
                    **evidence,
                },
                created_at=updated_at,
            )
        logger.info(
            "workflow sync reused skill_id=%s workflow_id=%s revision=%s generator_id=%s generator_version=%s skill_version_id=%s actor=%s mode=%s",
            skill["id"],
            workflow["id"],
            workflow["revision"],
            sync["generator_id"],
            sync["generator_version"],
            sync["skill_version_id"],
            actor,
            mode,
        )
        return {
            "mode": mode,
            "skill_id": skill["id"],
            "skill_version_id": sync["skill_version_id"],
            "workflow_revision": workflow["revision"],
            **evidence,
        }
