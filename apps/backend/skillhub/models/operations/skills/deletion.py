from __future__ import annotations

from sqlalchemy import delete, insert, or_, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, NotFoundError
from skillhub.models.schema import orm

ACTIVE_JOB_STATUSES = ("queued", "running")
ACTIVE_EVAL_STATUSES = ("queued", "running")
ACTIVE_PUBLISH_STATUSES = ("queued", "releasing")


class SkillDeletionMixin:
    def delete_skill(self, *, skill_id: str, confirmation_slug: str, actor: str) -> None:
        deleted_at = utc_now()
        with self._write_session() as session:
            skill = (
                session.execute(
                    orm.select_entity(orm.Skill)
                    .where(orm.Skill.id == skill_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if skill is None:
                raise NotFoundError(f"Skill not found: {skill_id}")
            self._require_skill_permission(
                session,
                skill_id=skill_id,
                actor=actor,
                permission="skill.delete",
            )
            if confirmation_slug != skill["slug"]:
                raise FieldInvariantError(
                    "Skill slug confirmation does not match.",
                    [
                        FieldError(
                            field="confirmation_slug",
                            message="输入当前 Skill slug 以确认永久删除。",
                            code="skill.delete_confirmation_mismatch",
                        )
                    ],
                )

            owned = self._skill_owned_ids(session, skill_id)
            related_job_ids = self._related_job_ids(session, owned)
            self._reject_active_work(session, owned, related_job_ids)
            artifact_ids = self._candidate_artifact_ids(session, owned)

            self._delete_skill_rows(session, skill_id, owned, related_job_ids)
            self._delete_unreferenced_artifacts(session, artifact_ids)
            session.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="skill.deleted",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={
                        "skill_id": skill_id,
                        "slug": skill["slug"],
                        "actor": actor,
                        "deleted_at": deleted_at.isoformat(),
                    },
                    created_at=deleted_at,
                )
            )

    def _skill_owned_ids(self, session, skill_id: str) -> dict[str, set[str]]:
        owned = {
            "versions": self._ids(session, select(orm.SkillVersion.id).where(orm.SkillVersion.skill_id == skill_id)),
            "eval_sets": self._ids(session, select(orm.EvalSet.id).where(orm.EvalSet.skill_id == skill_id)),
            "eval_cases": self._ids(session, select(orm.EvalCase.id).where(orm.EvalCase.skill_id == skill_id)),
            "case_versions": self._ids(session, select(orm.EvalCaseVersion.id).where(orm.EvalCaseVersion.skill_id == skill_id)),
            "eval_runs": self._ids(session, select(orm.EvalRun.id).where(orm.EvalRun.skill_id == skill_id)),
            "case_runs": self._ids(session, select(orm.EvalCaseRun.id).where(orm.EvalCaseRun.skill_id == skill_id)),
            "reviews": self._ids(session, select(orm.ReviewRequest.id).where(orm.ReviewRequest.skill_id == skill_id)),
            "publish_records": self._ids(session, select(orm.PublishRecord.id).where(orm.PublishRecord.skill_id == skill_id)),
            "workflows": self._ids(session, select(orm.Workflow.id).where(orm.Workflow.skill_id == skill_id)),
            "groups": self._ids(
                session,
                select(orm.Group.id)
                .where(orm.Group.scope_type == "skill")
                .where(orm.Group.scope_id == skill_id),
            ),
        }
        owned["workflow_syncs"] = self._ids(
            session,
            select(orm.WorkflowSync.id).where(orm.WorkflowSync.workflow_id.in_(owned["workflows"])),
        )
        return owned

    def _related_job_ids(self, session, owned: dict[str, set[str]]) -> set[str]:
        job_ids = self._ids(
            session,
            select(orm.EvalCaseRun.job_id)
            .where(orm.EvalCaseRun.id.in_(owned["case_runs"]))
            .where(orm.EvalCaseRun.job_id.is_not(None)),
        )
        if owned["publish_records"]:
            job_ids.update(
                self._ids(
                    session,
                    select(orm.Job.id)
                    .where(orm.Job.type == "publish_release")
                    .where(orm.Job.payload["publish_record_id"].as_string().in_(owned["publish_records"])),
                )
            )
        return job_ids

    def _reject_active_work(self, session, owned: dict[str, set[str]], job_ids: set[str]) -> None:
        active_eval = session.execute(
            select(orm.EvalCaseRun.id)
            .where(orm.EvalCaseRun.id.in_(owned["case_runs"]))
            .where(orm.EvalCaseRun.status.in_(ACTIVE_EVAL_STATUSES))
            .limit(1)
        ).scalar_one_or_none()
        active_publish = session.execute(
            select(orm.PublishRecord.id)
            .where(orm.PublishRecord.id.in_(owned["publish_records"]))
            .where(orm.PublishRecord.status.in_(ACTIVE_PUBLISH_STATUSES))
            .limit(1)
        ).scalar_one_or_none()
        active_job = session.execute(
            select(orm.Job.id)
            .where(orm.Job.id.in_(job_ids))
            .where(orm.Job.status.in_(ACTIVE_JOB_STATUSES))
            .limit(1)
        ).scalar_one_or_none()
        if active_eval or active_publish or active_job:
            raise ConflictError("Skill 存在排队中或运行中的任务，任务结束后才能永久删除。")

    def _candidate_artifact_ids(self, session, owned: dict[str, set[str]]) -> set[str]:
        artifact_ids: set[str] = set()
        refs = session.execute(
            select(orm.SkillVersion.content_ref).where(orm.SkillVersion.id.in_(owned["versions"]))
        ).scalars()
        for content_ref in refs:
            locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
            if isinstance(locator, str) and locator.startswith("artifact:"):
                artifact_ids.add(locator.removeprefix("artifact:"))
        artifact_sources = (
            (orm.EvalCaseVersion.workspace_artifact_id, orm.EvalCaseVersion.id, owned["case_versions"]),
            (orm.EvalRun.result_artifact_id, orm.EvalRun.id, owned["eval_runs"]),
            (orm.CaseResult.result_artifact_id, orm.CaseResult.run_id, owned["eval_runs"]),
            (orm.EvalCaseRun.result_artifact_id, orm.EvalCaseRun.id, owned["case_runs"]),
            (orm.WorkflowSync.source_artifact_id, orm.WorkflowSync.id, owned["workflow_syncs"]),
        )
        for artifact_column, owner_column, owner_ids in artifact_sources:
            artifact_ids.update(
                self._ids(
                    session,
                    select(artifact_column)
                    .where(owner_column.in_(owner_ids))
                    .where(artifact_column.is_not(None)),
                )
            )
        return artifact_ids

    def _delete_skill_rows(self, session, skill_id: str, owned: dict[str, set[str]], job_ids: set[str]) -> None:
        session.execute(
            update(orm.SkillBuilderSession)
            .where(
                or_(
                    orm.SkillBuilderSession.created_skill_id == skill_id,
                    orm.SkillBuilderSession.created_skill_version_id.in_(owned["versions"]),
                )
            )
            .values(created_skill_id=None, created_skill_version_id=None)
        )
        if job_ids:
            session.execute(
                update(orm.WorkerHeartbeat)
                .where(orm.WorkerHeartbeat.current_job_id.in_(job_ids))
                .values(status="idle", current_job_id=None, current_job_type=None, current_run_id=None)
            )
        self._delete_resource_history(session, skill_id, owned)

        session.execute(delete(orm.AcceptedVerification).where(orm.AcceptedVerification.skill_id == skill_id))
        session.execute(delete(orm.CaseResult).where(orm.CaseResult.skill_id == skill_id))
        session.execute(delete(orm.EvalCaseRun).where(orm.EvalCaseRun.skill_id == skill_id))
        session.execute(delete(orm.Job).where(orm.Job.id.in_(job_ids)))
        session.execute(delete(orm.EvalRun).where(orm.EvalRun.skill_id == skill_id))
        session.execute(delete(orm.EvalSetCase).where(orm.EvalSetCase.skill_id == skill_id))
        session.execute(update(orm.EvalCase).where(orm.EvalCase.skill_id == skill_id).values(current_version_id=None))
        session.execute(delete(orm.EvalCaseVersion).where(orm.EvalCaseVersion.skill_id == skill_id))
        session.execute(delete(orm.EvalCase).where(orm.EvalCase.skill_id == skill_id))
        session.execute(delete(orm.EvalSet).where(orm.EvalSet.skill_id == skill_id))

        session.execute(delete(orm.ReviewResponse).where(orm.ReviewResponse.skill_id == skill_id))
        session.execute(delete(orm.ReviewCheckResult).where(orm.ReviewCheckResult.skill_id == skill_id))
        session.execute(delete(orm.PublishRecord).where(orm.PublishRecord.skill_id == skill_id))
        session.execute(delete(orm.ReviewRequestPublishTarget).where(orm.ReviewRequestPublishTarget.skill_id == skill_id))
        session.execute(delete(orm.ReviewRequestReviewer).where(orm.ReviewRequestReviewer.skill_id == skill_id))
        session.execute(delete(orm.ReviewRequest).where(orm.ReviewRequest.skill_id == skill_id))

        session.execute(delete(orm.WorkflowSync).where(orm.WorkflowSync.id.in_(owned["workflow_syncs"])))
        session.execute(delete(orm.Workflow).where(orm.Workflow.skill_id == skill_id))
        session.execute(delete(orm.SavedView).where(orm.SavedView.skill_id == skill_id))
        session.execute(delete(orm.SkillTag).where(orm.SkillTag.skill_id == skill_id))
        session.execute(
            delete(orm.RoleAssignment).where(
                or_(
                    (orm.RoleAssignment.resource_type == "skill") & (orm.RoleAssignment.resource_id == skill_id),
                    (orm.RoleAssignment.subject_type == "group") & (orm.RoleAssignment.subject_id.in_(owned["groups"])),
                )
            )
        )
        session.execute(delete(orm.GroupMembership).where(orm.GroupMembership.group_id.in_(owned["groups"])))
        session.execute(delete(orm.Group).where(orm.Group.id.in_(owned["groups"])))
        session.execute(update(orm.Skill).where(orm.Skill.id == skill_id).values(current_version_id=None))
        session.execute(delete(orm.SkillVersion).where(orm.SkillVersion.skill_id == skill_id))
        session.execute(delete(orm.Skill).where(orm.Skill.id == skill_id))

    def _delete_resource_history(self, session, skill_id: str, owned: dict[str, set[str]]) -> None:
        resources = {
            "skill": {skill_id},
            "skill_version": owned["versions"],
            "eval_set": owned["eval_sets"],
            "eval_case": owned["eval_cases"],
            "eval_case_run": owned["case_runs"],
            "eval_run": owned["eval_runs"],
            "review_request": owned["reviews"],
            "publish_record": owned["publish_records"],
            "workflow": owned["workflows"],
            "group": owned["groups"],
        }
        notification_conditions = [
            (orm.Notification.resource_type == resource_type) & orm.Notification.resource_id.in_(resource_ids)
            for resource_type, resource_ids in resources.items()
            if resource_ids
        ]
        if notification_conditions:
            session.execute(delete(orm.Notification).where(or_(*notification_conditions)))
        audit_conditions = [
            (orm.AuditEvent.resource_type == resource_type) & orm.AuditEvent.resource_id.in_(resource_ids)
            for resource_type, resource_ids in resources.items()
            if resource_ids
        ]
        session.execute(delete(orm.AuditEvent).where(or_(*audit_conditions)))

    def _delete_unreferenced_artifacts(self, session, artifact_ids: set[str]) -> None:
        if not artifact_ids:
            return
        referenced: set[str] = set()
        locators = {f"artifact:{artifact_id}" for artifact_id in artifact_ids}
        remaining_refs = session.execute(
            select(orm.SkillVersion.content_ref).where(
                orm.SkillVersion.content_ref["locator"].as_string().in_(locators)
            )
        ).scalars()
        for content_ref in remaining_refs:
            locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
            if isinstance(locator, str):
                referenced.add(locator.removeprefix("artifact:"))
        columns = (
            orm.EvalCaseVersion.workspace_artifact_id,
            orm.EvalRun.result_artifact_id,
            orm.CaseResult.result_artifact_id,
            orm.EvalCaseRun.result_artifact_id,
            orm.WorkflowSync.source_artifact_id,
        )
        for column in columns:
            referenced.update(self._ids(session, select(column).where(column.in_(artifact_ids))))
        session.execute(delete(orm.Artifact).where(orm.Artifact.id.in_(artifact_ids - referenced)))

    def _ids(self, session, statement) -> set[str]:
        return {str(value) for value in session.execute(statement).scalars() if value is not None}
