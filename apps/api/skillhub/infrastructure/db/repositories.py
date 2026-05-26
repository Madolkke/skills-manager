from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import json
from typing import Any

from sqlalchemy import Engine, and_, delete, desc, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.application.run_comparison import build_run_case_comparisons, build_run_comparison_summary
from skillhub.application.run_matrix import build_eval_run_matrix
from skillhub.application.saved_views import normalize_saved_view_config, validate_saved_view_type
from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError, NotFoundError, PermissionDeniedError
from skillhub.domain.models import ContentRef, digest_text, new_id, normalize_tags, utc_now
from skillhub.domain.permissions import ROLE_PERMISSIONS, VALID_ROLES, permission_label, role_allows
from skillhub.infrastructure.db import tables


@dataclass(frozen=True)
class CreateSkillResult:
    skill_id: str
    skill_version_id: str
    eval_set_id: str
    eval_set_version_id: str
    version_number: int


@dataclass(frozen=True)
class CreateSkillVersionResult:
    skill_id: str
    skill_version_id: str
    version_number: int


@dataclass(frozen=True)
class CreateEvalCaseResult:
    skill_id: str
    eval_set_id: str
    eval_set_version_id: str
    eval_case_id: str
    eval_case_version_id: str
    input_artifact_id: str
    expected_output_artifact_id: str


@dataclass(frozen=True)
class CreatedEvalCaseResult:
    eval_case_id: str
    eval_case_version_id: str
    input_artifact_id: str
    expected_output_artifact_id: str


@dataclass(frozen=True)
class CreateEvalCasesBatchResult:
    skill_id: str
    eval_set_id: str
    eval_set_version_id: str
    created: tuple[CreatedEvalCaseResult, ...]


@dataclass(frozen=True)
class RecordEvalRunResult:
    eval_run_id: str
    skill_id: str
    skill_version_id: str
    eval_set_version_id: str
    passed: int
    failed: int
    total: int
    environment_tags: tuple[str, ...]
    run_context: dict[str, Any]
    run_context_hash: str


@dataclass(frozen=True)
class EvalSetVersionDetail:
    eval_set_version: dict[str, Any]
    eval_set: dict[str, Any]
    cases: list[dict[str, Any]]


@dataclass(frozen=True)
class EvalRunDetail:
    eval_run: dict[str, Any]
    skill: dict[str, Any]
    skill_version: dict[str, Any]
    eval_set_version: dict[str, Any]
    case_results: list[dict[str, Any]]


class SqlSkillRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
    ) -> CreateSkillResult:
        created_at = utc_now()
        skill_id = new_id("skill")
        skill_version_id = new_id("skillver")
        eval_set_id = new_id("evalset")
        eval_set_version_id = new_id("evalsetver")

        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(tables.skills).values(
                        id=skill_id,
                        slug=slug,
                        owner_ref=owner_ref,
                        current_version_id=None,
                        lifecycle_status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                connection.execute(
                    insert(tables.skill_versions).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=1,
                        content_ref=self._content_ref_payload(content_ref),
                        content_digest=content_ref.digest,
                        change_summary=change_summary,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(current_version_id=skill_version_id, updated_at=created_at)
                )
                connection.execute(
                    insert(tables.eval_sets).values(
                        id=eval_set_id,
                        skill_id=skill_id,
                        name="Primary",
                        description="Primary regression suite",
                        current_version_id=None,
                        lifecycle_status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                connection.execute(
                    insert(tables.eval_set_versions).values(
                        id=eval_set_version_id,
                        skill_id=skill_id,
                        eval_set_id=eval_set_id,
                        version_number=1,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(tables.eval_sets)
                    .where(tables.eval_sets.c.id == eval_set_id)
                    .values(current_version_id=eval_set_version_id, updated_at=created_at)
                )
                self._grant_skill_role(
                    connection,
                    skill_id=skill_id,
                    subject_id=actor,
                    role="owner",
                    actor=actor,
                    created_at=created_at,
                )
                connection.execute(
                    insert(tables.audit_events).values(
                        id=new_id("audit"),
                        actor_ref=actor,
                        action="role.assigned",
                        resource_type="skill",
                        resource_id=skill_id,
                        payload={"subject_type": "user", "subject_id": actor, "role": "owner", "reason": "skill.creator"},
                        created_at=created_at,
                    )
                )
        except IntegrityError as exc:
            raise skill_slug_conflict(slug) from exc

        return CreateSkillResult(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            eval_set_version_id=eval_set_version_id,
            version_number=1,
        )

    def create_skill_version(
        self,
        *,
        skill_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
    ) -> CreateSkillVersionResult:
        created_at = utc_now()
        skill_version_id = new_id("skillver")
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            version_number = self._next_skill_version_number(connection, skill_id)
            connection.execute(
                insert(tables.skill_versions).values(
                    id=skill_version_id,
                    skill_id=skill_id,
                    version_number=version_number,
                    content_ref=self._content_ref_payload(content_ref),
                    content_digest=content_ref.digest,
                    change_summary=change_summary,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            if make_current:
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(current_version_id=skill_version_id, updated_at=created_at)
                )
        return CreateSkillVersionResult(skill_id=skill_id, skill_version_id=skill_version_id, version_number=version_number)

    def update_skill(self, *, skill_id: str, slug: str, owner_ref: str) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(slug=slug, owner_ref=owner_ref, updated_at=updated_at)
                )
                return self._row_dict(self._skill_row(connection, skill_id))
        except IntegrityError as exc:
            raise skill_slug_conflict(slug) from exc

    def archive_skill(self, *, skill_id: str, actor: str) -> None:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            connection.execute(
                update(tables.skills)
                .where(tables.skills.c.id == skill_id)
                .values(lifecycle_status="archived", updated_at=updated_at)
            )
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="skill.archived",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={"skill_id": skill_id},
                    created_at=updated_at,
                )
            )

    def create_text_artifact(self, *, kind: str, namespace: str, content: str, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        with self.engine.begin() as connection:
            artifact_id = self._insert_text_artifact(
                connection,
                kind=kind,
                namespace=namespace,
                content=content,
                actor=actor,
                created_at=created_at,
            )
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one()
        return self._row_dict(artifact)

    def update_eval_case_title(self, *, case_id: str, title: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            self._eval_case_row(connection, case_id)
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == case_id)
                .values(title=title, updated_at=updated_at)
            )
            return self._row_dict(self._eval_case_row(connection, case_id))

    def archive_eval_case(self, *, case_id: str, actor: str) -> CreateEvalCaseResult:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == case_id)
                .values(lifecycle_status="archived", updated_at=updated_at)
            )
            next_case_version_ids = [
                case_version_id
                for case_version_id in self._eval_set_case_version_ids(connection, current_eval_set_version["id"])
                if self._eval_case_version_row(connection, case_version_id)["case_id"] != case_id
            ]
            eval_set_version_id = self._create_eval_set_version(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_version_ids=next_case_version_ids,
                created_at=updated_at,
                actor=actor,
            )
        return CreateEvalCaseResult(skill_id, eval_set["id"], eval_set_version_id, case_id, eval_case["current_version_id"], "", "")

    def create_eval_case(
        self,
        *,
        skill_id: str,
        title: str,
        input_text: str,
        expected_output: str,
        actor: str,
        notes: str | None = None,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_id = new_id("case")
        eval_case_version_id = new_id("casever")
        with self.engine.begin() as connection:
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            input_artifact_id = self._insert_text_artifact(
                connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
            )
            expected_output_artifact_id = self._insert_text_artifact(
                connection,
                kind="expected_output",
                namespace=skill_id,
                content=expected_output,
                actor=actor,
                created_at=created_at,
            )
            connection.execute(
                insert(tables.eval_cases).values(
                    id=eval_case_id,
                    skill_id=skill_id,
                    title=title,
                    current_version_id=None,
                    lifecycle_status="active",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=eval_case_id,
                    version_number=1,
                    input_artifact_id=input_artifact_id,
                    expected_output_artifact_id=expected_output_artifact_id,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == eval_case_id)
                .values(current_version_id=eval_case_version_id, updated_at=created_at)
            )
            eval_set_version_id = self._create_eval_set_version(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_version_ids=[
                    *self._eval_set_case_version_ids(connection, current_eval_set_version["id"]),
                    eval_case_version_id,
                ],
                created_at=created_at,
                actor=actor,
            )
        return CreateEvalCaseResult(
            skill_id,
            eval_set["id"],
            eval_set_version_id,
            eval_case_id,
            eval_case_version_id,
            input_artifact_id,
            expected_output_artifact_id,
        )

    def create_eval_cases_batch(self, *, skill_id: str, cases: list[dict[str, Any]], actor: str) -> CreateEvalCasesBatchResult:
        if not cases:
            raise InvariantError("At least one eval case is required.")
        created_at = utc_now()
        created_cases: list[CreatedEvalCaseResult] = []
        with self.engine.begin() as connection:
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            for item in cases:
                title = self._required_text(item, "title")
                input_text = self._required_text(item, "input_text")
                expected_output = self._required_text(item, "expected_output")
                if not title or not input_text or not expected_output:
                    raise InvariantError("Each eval case requires title, input_text, and expected_output.")
                eval_case_id = new_id("case")
                eval_case_version_id = new_id("casever")
                input_artifact_id = self._insert_text_artifact(
                    connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
                )
                expected_output_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="expected_output",
                    namespace=skill_id,
                    content=expected_output,
                    actor=actor,
                    created_at=created_at,
                )
                connection.execute(
                    insert(tables.eval_cases).values(
                        id=eval_case_id,
                        skill_id=skill_id,
                        title=title,
                        current_version_id=None,
                        lifecycle_status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                connection.execute(
                    insert(tables.eval_case_versions).values(
                        id=eval_case_version_id,
                        skill_id=skill_id,
                        case_id=eval_case_id,
                        version_number=1,
                        input_artifact_id=input_artifact_id,
                        expected_output_artifact_id=expected_output_artifact_id,
                        notes=item.get("notes"),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == eval_case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
                created_cases.append(
                    CreatedEvalCaseResult(eval_case_id, eval_case_version_id, input_artifact_id, expected_output_artifact_id)
                )
            eval_set_version_id = self._create_eval_set_version(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_version_ids=[
                    *self._eval_set_case_version_ids(connection, current_eval_set_version["id"]),
                    *[item.eval_case_version_id for item in created_cases],
                ],
                created_at=created_at,
                actor=actor,
            )
        return CreateEvalCasesBatchResult(skill_id, eval_set["id"], eval_set_version_id, tuple(created_cases))

    def create_eval_case_version(
        self,
        *,
        case_id: str,
        input_text: str,
        expected_output: str,
        actor: str,
        notes: str | None = None,
        make_current: bool = True,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_version_id = new_id("casever")
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            version_number = self._next_eval_case_version_number(connection, case_id)
            input_artifact_id = self._insert_text_artifact(
                connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
            )
            expected_output_artifact_id = self._insert_text_artifact(
                connection,
                kind="expected_output",
                namespace=skill_id,
                content=expected_output,
                actor=actor,
                created_at=created_at,
            )
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=case_id,
                    version_number=version_number,
                    input_artifact_id=input_artifact_id,
                    expected_output_artifact_id=expected_output_artifact_id,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            eval_set = self._primary_eval_set_row(connection, skill_id)
            eval_set_version_id = eval_set["current_version_id"]
            if make_current:
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
                current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
                eval_set_version_id = self._create_eval_set_version(
                    connection,
                    skill_id=skill_id,
                    eval_set_id=eval_set["id"],
                    case_version_ids=[
                        eval_case_version_id
                        if self._eval_case_version_row(connection, item)["case_id"] == case_id
                        else item
                        for item in self._eval_set_case_version_ids(connection, current_eval_set_version["id"])
                    ],
                    created_at=created_at,
                    actor=actor,
                )
        return CreateEvalCaseResult(
            skill_id, eval_set["id"], eval_set_version_id, case_id, eval_case_version_id, input_artifact_id, expected_output_artifact_id
        )

    def restore_eval_case_version(
        self,
        *,
        case_id: str,
        source_case_version_id: str,
        actor: str,
        notes: str | None = None,
    ) -> CreateEvalCaseResult:
        with self.engine.connect() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            if eval_case["lifecycle_status"] != "active":
                raise InvariantError("Archived eval cases cannot be restored.")
            source_case_version = self._eval_case_version_row(connection, source_case_version_id)
            if source_case_version["case_id"] != case_id:
                raise NotFoundError(f"EvalCaseVersion not found for case: {source_case_version_id}")
            source_detail = self._case_version_detail(connection, source_case_version)
        input_text = source_detail["input_artifact"].get("content_text")
        expected_output = source_detail["expected_output_artifact"].get("content_text")
        if input_text is None or expected_output is None:
            raise InvariantError("Only text eval case versions can be restored.")
        return self.create_eval_case_version(
            case_id=case_id,
            input_text=input_text,
            expected_output=expected_output,
            actor=actor,
            notes=notes if notes is not None else f"Restored from case v{source_case_version['version_number']}.",
            make_current=True,
        )

    def record_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_version_id: str,
        strategy: str,
        results: dict[str, Any],
        actor: str,
        environment_tags: list[str] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> RecordEvalRunResult:
        created_at = utc_now()
        eval_run_id = new_id("evalrun")
        tags = normalize_tags(environment_tags or [])
        context = self._canonical_json_object(run_context or {})
        context_hash = self._run_context_hash(tags, context)

        with self.engine.begin() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set_version = self._eval_set_version_row(connection, eval_set_version_id)
            if skill_version["skill_id"] != eval_set_version["skill_id"]:
                raise InvariantError("EvalRun must bind a skill version and eval set version from the same skill.")
            skill_id = skill_version["skill_id"]
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_version_id)
            normalized_results = self._normalize_eval_run_results(case_version_ids, results)
            passed_count = sum(1 for case_version_id in case_version_ids if normalized_results[case_version_id]["passed"])
            failed_count = len(case_version_ids) - passed_count
            summary = {"passed": passed_count, "failed": failed_count, "total": len(case_version_ids)}
            result_artifact_ids = {
                case_version_id: self._insert_text_artifact(
                    connection,
                    kind="actual_output",
                    namespace=f"eval_run:{eval_run_id}",
                    content=result["actual_output"],
                    actor=actor,
                    created_at=created_at,
                )
                for case_version_id, result in normalized_results.items()
                if result["actual_output"].strip()
            }
            connection.execute(
                insert(tables.eval_runs).values(
                    id=eval_run_id,
                    skill_id=skill_id,
                    skill_version_id=skill_version_id,
                    eval_set_version_id=eval_set_version_id,
                    strategy=strategy,
                    status="finished",
                    environment_tags=list(tags),
                    run_context=context,
                    run_context_hash=context_hash,
                    summary=summary,
                    result_artifact_id=None,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                insert(tables.case_results),
                [
                    {
                        "run_id": eval_run_id,
                        "skill_id": skill_id,
                        "case_version_id": case_version_id,
                        "passed": normalized_results[case_version_id]["passed"],
                        "score": 1 if normalized_results[case_version_id]["passed"] else 0,
                        "result_artifact_id": result_artifact_ids.get(case_version_id),
                        "created_at": created_at,
                    }
                    for case_version_id in case_version_ids
                ],
            )
        return RecordEvalRunResult(
            eval_run_id,
            skill_id,
            skill_version_id,
            eval_set_version_id,
            passed_count,
            failed_count,
            len(case_version_ids),
            tags,
            context,
            context_hash,
        )

    def list_skills(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(tables.skills)
                    .where(tables.skills.c.lifecycle_status == "active")
                    .order_by(tables.skills.c.slug)
                )
                .mappings()
                .all()
            )
            return [
                {
                    "skill": self._row_dict(row),
                    "summary": self._skill_summary(connection, row),
                }
                for row in rows
            ]

    def skill_detail(self, skill_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            version_rows = (
                connection.execute(
                    select(tables.skill_versions)
                    .where(tables.skill_versions.c.skill_id == skill_id)
                    .order_by(desc(tables.skill_versions.c.version_number))
                )
                .mappings()
                .all()
            )
            versions = [self._skill_version_detail(connection, row) for row in version_rows]
            eval_sets = [
                self._eval_set_summary(connection, row)
                for row in connection.execute(
                    select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill_id).order_by(tables.eval_sets.c.name)
                )
                .mappings()
                .all()
            ]
            latest_runs = [
                self._row_dict(row)
                for row in connection.execute(
                    select(tables.eval_runs)
                    .where(tables.eval_runs.c.skill_id == skill_id)
                    .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                    .limit(10)
                )
                .mappings()
                .all()
            ]
            summary = self._skill_summary(connection, skill)
            role_assignments = self._skill_role_assignments(connection, skill_id)
            audit_events = self._skill_audit_events(connection, skill_id, limit=10)
        return {
            "skill": self._row_dict(skill),
            "summary": summary,
            "versions": versions,
            "eval_sets": eval_sets,
            "latest_eval_runs": latest_runs,
            "role_assignments": role_assignments,
            "audit_events": audit_events,
        }

    def list_skill_role_assignments(self, *, skill_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_role_assignments(connection, skill_id)

    def skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        permissions = sorted({permission for role_permissions in ROLE_PERMISSIONS.values() for permission in role_permissions})
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            roles = sorted(self._actor_skill_roles(connection, skill_id=skill_id, actor=actor))
        return {
            "actor": actor,
            "subject_type": subject_type,
            "roles": roles,
            "permissions": {permission: any(role_allows(role, permission) for role in roles) for permission in permissions},
        }

    def assign_skill_role(
        self,
        *,
        skill_id: str,
        subject_id: str,
        role: str,
        actor: str,
        subject_type: str = "user",
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            assignment = self._grant_skill_role(connection, skill_id, subject_id, role, actor, created_at, subject_type)
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="role.assigned",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={key: assignment[key] for key in ["id", "subject_type", "subject_id", "role"]},
                    created_at=created_at,
                )
            )
        return assignment

    def revoke_role_assignment(self, *, role_assignment_id: str, actor: str) -> dict[str, bool]:
        revoked_at = utc_now()
        with self.engine.begin() as connection:
            assignment = self._role_assignment_row(connection, role_assignment_id)
            if assignment["resource_type"] != "skill":
                raise InvariantError("Only skill role assignments can be revoked.")
            skill_id = assignment["resource_id"]
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            if assignment["role"] == "owner" and self._skill_owner_count(connection, skill_id) <= 1:
                raise InvariantError("Cannot revoke the last owner for a skill.")
            connection.execute(delete(tables.role_assignments).where(tables.role_assignments.c.id == role_assignment_id))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="role.revoked",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={
                        "role_assignment_id": role_assignment_id,
                        "subject_type": assignment["subject_type"],
                        "subject_id": assignment["subject_id"],
                        "role": assignment["role"],
                    },
                    created_at=revoked_at,
                )
            )
        return {"ok": True}

    def list_skill_audit_events(
        self,
        *,
        skill_id: str,
        limit: int = 50,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_audit_events(connection, skill_id, limit=limit, actor=actor, action=action, resource_type=resource_type)

    def eval_set_version_detail(self, eval_set_version_id: str) -> EvalSetVersionDetail:
        with self.engine.connect() as connection:
            eval_set_version = self._eval_set_version_row(connection, eval_set_version_id)
            eval_set = (
                connection.execute(select(tables.eval_sets).where(tables.eval_sets.c.id == eval_set_version["eval_set_id"]))
                .mappings()
                .one()
            )
            cases = self._eval_set_cases(connection, eval_set_version_id)
        return EvalSetVersionDetail(self._row_dict(eval_set_version), self._row_dict(eval_set), cases)

    def eval_run_detail(self, eval_run_id: str) -> EvalRunDetail:
        with self.engine.connect() as connection:
            eval_run = self._eval_run_row(connection, eval_run_id)
            skill = self._skill_row(connection, eval_run["skill_id"])
            skill_version = self._skill_version_row(connection, eval_run["skill_version_id"])
            eval_set_version = self._eval_set_version_row(connection, eval_run["eval_set_version_id"])
            case_results = []
            for result in (
                connection.execute(
                    select(tables.case_results)
                    .where(tables.case_results.c.run_id == eval_run_id)
                    .order_by(tables.case_results.c.case_version_id)
                )
                .mappings()
                .all()
            ):
                case_version = self._eval_case_version_row(connection, result["case_version_id"])
                eval_case = self._eval_case_row(connection, case_version["case_id"])
                result_artifact = None
                if result["result_artifact_id"] is not None:
                    result_artifact = (
                        connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == result["result_artifact_id"]))
                        .mappings()
                        .one_or_none()
                    )
                case_results.append(
                    {
                        "result": self._row_dict(result),
                        "result_artifact": self._row_dict(result_artifact) if result_artifact is not None else None,
                        "case": self._row_dict(eval_case),
                        "case_version": self._case_version_detail(connection, case_version),
                    }
                )
            skill_version_detail = self._skill_version_detail(connection, skill_version)
        return EvalRunDetail(self._row_dict(eval_run), self._row_dict(skill), skill_version_detail, self._row_dict(eval_set_version), case_results)

    def list_eval_runs_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_version_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            rows = self._filtered_eval_run_rows(connection, skill_id, skill_version_id, eval_set_version_id, strategy, status, limit)
            runs = [self._eval_run_context_row(connection, row, include_accepted=True) for row in rows]
        return {"skill": self._row_dict(skill), "runs": runs}

    def eval_run_matrix_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_version_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            rows = self._filtered_eval_run_rows(connection, skill_id, skill_version_id, eval_set_version_id, strategy, status, limit)
            runs = [self._eval_run_context_row(connection, row, include_accepted=False) for row in rows]
            eval_set_cases_by_run = {row["id"]: self._eval_set_cases(connection, row["eval_set_version_id"]) for row in rows}
            results_by_run = {
                row["id"]: [
                    self._row_dict(result)
                    for result in connection.execute(select(tables.case_results).where(tables.case_results.c.run_id == row["id"]))
                    .mappings()
                    .all()
                ]
                for row in rows
            }
        return build_eval_run_matrix(skill=self._row_dict(skill), runs=runs, eval_set_cases_by_run=eval_set_cases_by_run, results_by_run=results_by_run)

    def list_saved_views(self, *, skill_id: str, view_type: str = "run_history") -> list[dict[str, Any]]:
        validate_saved_view_type(view_type)
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            rows = (
                connection.execute(
                    select(tables.saved_views)
                    .where(tables.saved_views.c.skill_id == skill_id)
                    .where(tables.saved_views.c.view_type == view_type)
                    .order_by(tables.saved_views.c.name, desc(tables.saved_views.c.created_at))
                )
                .mappings()
                .all()
            )
        return [self._row_dict(row) for row in rows]

    def create_saved_view(
        self,
        *,
        skill_id: str,
        name: str,
        view_type: str,
        config: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        validate_saved_view_type(view_type)
        clean_name = name.strip()
        if not clean_name:
            raise FieldInvariantError("Saved view name is required.", [FieldError("name", "填写保存视图名称。", "saved_view.name_required")])
        values = {
            "id": new_id("view"),
            "skill_id": skill_id,
            "name": clean_name,
            "view_type": view_type,
            "config": normalize_saved_view_config(config),
            "created_at": utc_now(),
            "created_by": actor,
        }
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                connection.execute(insert(tables.saved_views).values(**values))
                row = connection.execute(select(tables.saved_views).where(tables.saved_views.c.id == values["id"])).mappings().one()
        except IntegrityError as exc:
            raise FieldInvariantError(
                f"Saved view name already exists: {clean_name}",
                [FieldError("name", "保存视图名称已存在。", "saved_view.name_conflict")],
            ) from exc
        return self._row_dict(row)

    def delete_saved_view(self, saved_view_id: str) -> dict[str, bool]:
        with self.engine.begin() as connection:
            result = connection.execute(tables.saved_views.delete().where(tables.saved_views.c.id == saved_view_id))
            if result.rowcount == 0:
                raise NotFoundError(f"SavedView not found: {saved_view_id}")
        return {"ok": True}

    def compare_eval_runs(self, *, baseline_run_id: str, candidate_run_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            baseline_run = self._eval_run_row(connection, baseline_run_id)
            candidate_run = self._eval_run_row(connection, candidate_run_id)
            if baseline_run["skill_id"] != candidate_run["skill_id"]:
                raise InvariantError("Run comparison requires runs from the same skill.")
            if baseline_run["eval_set_version_id"] != candidate_run["eval_set_version_id"]:
                raise InvariantError("Run comparison requires the same EvalSetVersion.")
            if baseline_run["status"] != "finished" or candidate_run["status"] != "finished":
                raise InvariantError("Run comparison requires finished runs.")
            skill = self._skill_row(connection, baseline_run["skill_id"])
            eval_set_version = self._eval_set_version_row(connection, baseline_run["eval_set_version_id"])
            eval_set = connection.execute(select(tables.eval_sets).where(tables.eval_sets.c.id == eval_set_version["eval_set_id"])).mappings().one()
            baseline_version = self._skill_version_row(connection, baseline_run["skill_version_id"])
            candidate_version = self._skill_version_row(connection, candidate_run["skill_version_id"])
            case_comparisons, comparison_summary = build_run_case_comparisons(
                eval_set_cases=self._eval_set_cases(connection, eval_set_version["id"]),
                baseline_results=self._case_results_by_case_version(connection, baseline_run["id"]),
                candidate_results=self._case_results_by_case_version(connection, candidate_run["id"]),
            )
            return {
                "skill": self._row_dict(skill),
                "eval_set": self._row_dict(eval_set),
                "eval_set_version": self._row_dict(eval_set_version),
                "baseline": {"eval_run": self._row_dict(baseline_run), "skill_version": self._row_dict(baseline_version)},
                "candidate": {"eval_run": self._row_dict(candidate_run), "skill_version": self._row_dict(candidate_version)},
                "summary": build_run_comparison_summary(
                    baseline_summary=baseline_run["summary"],
                    candidate_summary=candidate_run["summary"],
                    comparison_summary=comparison_summary,
                ),
                "case_comparisons": case_comparisons,
                "candidate_accepted_verification": self._accepted_verification_for_eval_run(connection, candidate_run["id"]),
            }

    def accept_eval_run_verification(self, *, eval_run_id: str, note: str, actor: str) -> dict[str, Any]:
        accepted_at = utc_now()
        with self.engine.begin() as connection:
            eval_run = self._eval_run_row(connection, eval_run_id)
            if eval_run["status"] != "finished":
                raise InvariantError("Accepted verification requires a finished eval run.")
            self._require_skill_permission(connection, skill_id=eval_run["skill_id"], actor=actor, permission="verification.accept")
            skill_version = self._skill_version_row(connection, eval_run["skill_version_id"])
            eval_set_version = self._eval_set_version_row(connection, eval_run["eval_set_version_id"])
            if skill_version["skill_id"] != eval_run["skill_id"] or eval_set_version["skill_id"] != eval_run["skill_id"]:
                raise InvariantError("Accepted verification requires same-skill records.")

            values = {
                "skill_id": eval_run["skill_id"],
                "skill_version_id": skill_version["id"],
                "eval_set_version_id": eval_set_version["id"],
                "run_context_hash": eval_run["run_context_hash"],
                "eval_run_id": eval_run["id"],
                "note": note.strip(),
                "created_at": accepted_at,
                "created_by": actor,
            }
            existing = self._accepted_verification_for_context(
                connection,
                skill_id=eval_run["skill_id"],
                skill_version_id=skill_version["id"],
                eval_set_version_id=eval_set_version["id"],
                run_context_hash=eval_run["run_context_hash"],
            )
            if existing is None:
                accepted_id = new_id("accepted")
                connection.execute(insert(tables.accepted_verifications).values(id=accepted_id, **values))
            else:
                accepted_id = existing["id"]
                connection.execute(update(tables.accepted_verifications).where(tables.accepted_verifications.c.id == accepted_id).values(**values))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="eval_run.accepted_verification_set",
                    resource_type="eval_run",
                    resource_id=eval_run["id"],
                    payload={
                        "accepted_verification_id": accepted_id,
                        "eval_run_id": eval_run["id"],
                        "skill_version_id": skill_version["id"],
                        "eval_set_version_id": eval_set_version["id"],
                        "run_context_hash": eval_run["run_context_hash"],
                    },
                    created_at=accepted_at,
                )
            )
            accepted = self._accepted_verification_row(connection, accepted_id)
        return self._row_dict(accepted)

    def eval_case_history(self, case_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            rows = (
                connection.execute(
                    select(tables.eval_case_versions)
                    .where(tables.eval_case_versions.c.case_id == case_id)
                    .order_by(desc(tables.eval_case_versions.c.version_number))
                )
                .mappings()
                .all()
            )
            versions = []
            for case_version in rows:
                memberships = (
                    connection.execute(
                        select(
                            tables.eval_set_case_versions.c.eval_set_version_id,
                            tables.eval_set_case_versions.c.position,
                            tables.eval_set_versions.c.eval_set_id,
                            tables.eval_set_versions.c.version_number,
                            tables.eval_set_versions.c.created_at,
                            tables.eval_set_versions.c.created_by,
                        )
                        .join(tables.eval_set_versions, tables.eval_set_case_versions.c.eval_set_version_id == tables.eval_set_versions.c.id)
                        .where(tables.eval_set_case_versions.c.case_version_id == case_version["id"])
                        .order_by(desc(tables.eval_set_versions.c.version_number))
                    )
                    .mappings()
                    .all()
                )
                versions.append(
                    {
                        "case_version": self._case_version_detail(connection, case_version),
                        "included_in_eval_set_versions": [
                            {
                                "id": membership["eval_set_version_id"],
                                "eval_set_id": membership["eval_set_id"],
                                "version_number": membership["version_number"],
                                "position": membership["position"],
                                "created_at": membership["created_at"],
                                "created_by": membership["created_by"],
                            }
                            for membership in memberships
                        ],
                    }
                )
        return {"case": self._row_dict(eval_case), "versions": versions}

    def bundle_diff(self, *, left_skill_version_id: str, right_skill_version_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            left_version = self._skill_version_row(connection, left_skill_version_id)
            right_version = self._skill_version_row(connection, right_skill_version_id)
            if left_version["skill_id"] != right_version["skill_id"]:
                raise InvariantError("Bundle diff requires skill versions from the same skill.")
            return self._bundle_diff_from_versions(connection, left_version, right_version)

    @staticmethod
    def _required_text(item: dict[str, Any], key: str) -> str:
        value = item.get(key)
        return value.strip() if isinstance(value, str) else ""

    def _normalize_eval_run_results(self, case_version_ids: list[str], results: dict[str, Any]) -> dict[str, dict[str, Any]]:
        expected_ids = set(case_version_ids)
        result_ids = set(results)
        field_errors = [
            FieldError(field=f"results.{case_version_id}", message="确认该测试用例通过或不通过。", code="eval_run.result_required")
            for case_version_id in case_version_ids
            if case_version_id not in result_ids
        ]
        field_errors.extend(
            FieldError(field=f"results.{case_version_id}", message="测试结果不属于当前 EvalSetVersion。", code="eval_run.result_unexpected")
            for case_version_id in sorted(result_ids - expected_ids)
        )
        if field_errors:
            raise FieldInvariantError("EvalRun results must exactly match the eval set version cases.", field_errors)
        normalized: dict[str, dict[str, Any]] = {}
        invalid_fields: list[FieldError] = []
        for case_version_id in case_version_ids:
            raw_result = results[case_version_id]
            if hasattr(raw_result, "model_dump"):
                raw_result = raw_result.model_dump()
            if isinstance(raw_result, bool):
                normalized[case_version_id] = {"passed": raw_result, "actual_output": ""}
                continue
            if isinstance(raw_result, dict) and isinstance(raw_result.get("passed"), bool):
                actual_output = raw_result.get("actual_output", "")
                if actual_output is None:
                    actual_output = ""
                if not isinstance(actual_output, str):
                    invalid_fields.append(
                        FieldError(
                            field=f"results.{case_version_id}.actual_output",
                            message="本次运行结果必须是文本。",
                            code="eval_run.actual_output_invalid",
                        )
                    )
                    continue
                normalized[case_version_id] = {"passed": raw_result["passed"], "actual_output": actual_output}
                continue
            invalid_fields.append(
                FieldError(field=f"results.{case_version_id}", message="确认该测试用例通过或不通过。", code="eval_run.result_invalid")
            )
        if invalid_fields:
            raise FieldInvariantError("EvalRun results must contain pass/fail values.", invalid_fields)
        return normalized

    def _filtered_eval_run_rows(
        self,
        connection,
        skill_id: str,
        skill_version_id: str | None,
        eval_set_version_id: str | None,
        strategy: str | None,
        status: str | None,
        limit: int,
    ):
        query = select(tables.eval_runs).where(tables.eval_runs.c.skill_id == skill_id)
        if skill_version_id:
            query = query.where(tables.eval_runs.c.skill_version_id == skill_version_id)
        if eval_set_version_id:
            query = query.where(tables.eval_runs.c.eval_set_version_id == eval_set_version_id)
        if strategy:
            query = query.where(tables.eval_runs.c.strategy == strategy)
        if status:
            query = query.where(tables.eval_runs.c.status == status)
        return (
            connection.execute(query.order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id)).limit(max(1, min(limit, 200))))
            .mappings()
            .all()
        )

    def _eval_run_context_row(self, connection, run, *, include_accepted: bool) -> dict[str, Any]:
        skill_version = self._skill_version_row(connection, run["skill_version_id"])
        eval_set_version = self._eval_set_version_row(connection, run["eval_set_version_id"])
        eval_set = connection.execute(select(tables.eval_sets).where(tables.eval_sets.c.id == eval_set_version["eval_set_id"])).mappings().one()
        row = {
            "eval_run": self._row_dict(run),
            "skill_version": self._row_dict(skill_version),
            "eval_set": self._row_dict(eval_set),
            "eval_set_version": self._row_dict(eval_set_version),
        }
        if include_accepted:
            row["accepted_verification"] = self._accepted_verification_for_eval_run(connection, run["id"])
        return row

    def _latest_finished_run(self, connection, *, skill_version_id: str, eval_set_version_id: str):
        return (
            connection.execute(
                select(tables.eval_runs)
                .where(tables.eval_runs.c.skill_version_id == skill_version_id)
                .where(tables.eval_runs.c.eval_set_version_id == eval_set_version_id)
                .where(tables.eval_runs.c.status == "finished")
                .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )

    def _case_results_by_case_version(self, connection, run_id: str) -> dict[str, bool]:
        return {
            row["case_version_id"]: row["passed"]
            for row in connection.execute(
                select(tables.case_results.c.case_version_id, tables.case_results.c.passed).where(tables.case_results.c.run_id == run_id)
            )
            .mappings()
            .all()
        }

    def _skill_row(self, connection, skill_id: str):
        row = connection.execute(select(tables.skills).where(tables.skills.c.id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return row

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

    def _eval_set_version_row(self, connection, eval_set_version_id: str):
        row = connection.execute(select(tables.eval_set_versions).where(tables.eval_set_versions.c.id == eval_set_version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalSetVersion not found: {eval_set_version_id}")
        return row

    def _eval_run_row(self, connection, eval_run_id: str):
        row = connection.execute(select(tables.eval_runs).where(tables.eval_runs.c.id == eval_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalRun not found: {eval_run_id}")
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
        eval_set_version_id: str,
        run_context_hash: str,
    ) -> dict[str, Any] | None:
        row = (
            connection.execute(
                select(tables.accepted_verifications)
                .where(tables.accepted_verifications.c.skill_id == skill_id)
                .where(tables.accepted_verifications.c.skill_version_id == skill_version_id)
                .where(tables.accepted_verifications.c.eval_set_version_id == eval_set_version_id)
                .where(tables.accepted_verifications.c.run_context_hash == run_context_hash)
            )
            .mappings()
            .one_or_none()
        )
        return self._row_dict(row) if row is not None else None

    def _role_assignment_row(self, connection, role_assignment_id: str):
        row = connection.execute(select(tables.role_assignments).where(tables.role_assignments.c.id == role_assignment_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"RoleAssignment not found: {role_assignment_id}")
        return row

    def _skill_role_assignments(self, connection, skill_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.role_assignments)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
                .order_by(tables.role_assignments.c.role, tables.role_assignments.c.subject_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _skill_audit_events(
        self,
        connection,
        skill_id: str,
        *,
        limit: int,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        skill_version_ids = select(tables.skill_versions.c.id).where(tables.skill_versions.c.skill_id == skill_id)
        eval_run_ids = select(tables.eval_runs.c.id).where(tables.eval_runs.c.skill_id == skill_id)
        conditions = [
            or_(
                and_(tables.audit_events.c.resource_type == "skill", tables.audit_events.c.resource_id == skill_id),
                and_(tables.audit_events.c.resource_type == "skill_version", tables.audit_events.c.resource_id.in_(skill_version_ids)),
                and_(tables.audit_events.c.resource_type == "eval_run", tables.audit_events.c.resource_id.in_(eval_run_ids)),
            )
        ]
        if actor:
            conditions.append(tables.audit_events.c.actor_ref == actor)
        if action:
            conditions.append(tables.audit_events.c.action == action)
        if resource_type:
            conditions.append(tables.audit_events.c.resource_type == resource_type)
        rows = (
            connection.execute(
                select(tables.audit_events)
                .where(*conditions)
                .order_by(desc(tables.audit_events.c.created_at), desc(tables.audit_events.c.id))
                .limit(max(1, min(limit, 200)))
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _grant_skill_role(
        self,
        connection,
        skill_id: str,
        subject_id: str,
        role: str,
        actor: str,
        created_at: datetime,
        subject_type: str = "user",
    ) -> dict[str, Any]:
        clean_subject_id = subject_id.strip()
        clean_subject_type = subject_type.strip() or "user"
        if not clean_subject_id:
            raise InvariantError("Role subject_id is required.")
        if role not in VALID_ROLES:
            raise InvariantError(f"Unsupported role: {role}")
        existing = (
            connection.execute(
                select(tables.role_assignments)
                .where(tables.role_assignments.c.subject_type == clean_subject_type)
                .where(tables.role_assignments.c.subject_id == clean_subject_id)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
                .where(tables.role_assignments.c.role == role)
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            return self._row_dict(existing)
        row = {
            "id": new_id("role"),
            "subject_type": clean_subject_type,
            "subject_id": clean_subject_id,
            "resource_type": "skill",
            "resource_id": skill_id,
            "role": role,
            "created_at": created_at,
            "created_by": actor,
        }
        connection.execute(insert(tables.role_assignments).values(**row))
        return row

    def _actor_skill_roles(self, connection, *, skill_id: str, actor: str) -> set[str]:
        return set(
            connection.execute(
                select(tables.role_assignments.c.role)
                .where(tables.role_assignments.c.subject_type == "user")
                .where(tables.role_assignments.c.subject_id == actor)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
            ).scalars()
        )

    def _require_skill_permission(self, connection, *, skill_id: str, actor: str, permission: str) -> None:
        roles = self._actor_skill_roles(connection, skill_id=skill_id, actor=actor)
        if any(role_allows(role, permission) for role in roles):
            return
        raise PermissionDeniedError(f"{permission} requires {permission_label(permission)} for this skill.")

    def _skill_owner_count(self, connection, skill_id: str) -> int:
        return len(
            list(
                connection.execute(
                    select(tables.role_assignments.c.id)
                    .where(tables.role_assignments.c.resource_type == "skill")
                    .where(tables.role_assignments.c.resource_id == skill_id)
                    .where(tables.role_assignments.c.role == "owner")
                ).scalars()
            )
        )

    def _next_skill_version_number(self, connection, skill_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.skill_versions.c.version_number).where(tables.skill_versions.c.skill_id == skill_id)).scalars(),
            default=0,
        )

    def _next_eval_case_version_number(self, connection, case_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.eval_case_versions.c.version_number).where(tables.eval_case_versions.c.case_id == case_id)).scalars(),
            default=0,
        )

    def _next_eval_set_version_number(self, connection, eval_set_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.eval_set_versions.c.version_number).where(tables.eval_set_versions.c.eval_set_id == eval_set_id)).scalars(),
            default=0,
        )

    def _create_eval_set_version(
        self,
        connection,
        *,
        skill_id: str,
        eval_set_id: str,
        case_version_ids: list[str],
        created_at: datetime,
        actor: str,
    ) -> str:
        eval_set_version_id = new_id("evalsetver")
        connection.execute(
            insert(tables.eval_set_versions).values(
                id=eval_set_version_id,
                skill_id=skill_id,
                eval_set_id=eval_set_id,
                version_number=self._next_eval_set_version_number(connection, eval_set_id),
                created_at=created_at,
                created_by=actor,
            )
        )
        if case_version_ids:
            connection.execute(
                insert(tables.eval_set_case_versions),
                [
                    {"eval_set_version_id": eval_set_version_id, "skill_id": skill_id, "case_version_id": case_version_id, "position": position}
                    for position, case_version_id in enumerate(case_version_ids)
                ],
            )
        connection.execute(
            update(tables.eval_sets)
            .where(tables.eval_sets.c.id == eval_set_id)
            .values(current_version_id=eval_set_version_id, updated_at=created_at)
        )
        return eval_set_version_id

    def _eval_set_case_version_ids(self, connection, eval_set_version_id: str) -> list[str]:
        return list(
            connection.execute(
                select(tables.eval_set_case_versions.c.case_version_id)
                .where(tables.eval_set_case_versions.c.eval_set_version_id == eval_set_version_id)
                .order_by(tables.eval_set_case_versions.c.position)
            ).scalars()
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

    def _content_ref_payload(self, content_ref: ContentRef) -> dict[str, str]:
        payload = {"kind": content_ref.kind, "locator": content_ref.locator, "digest": content_ref.digest}
        if content_ref.path is not None:
            payload["path"] = content_ref.path
        return payload

    def _skill_summary(self, connection, skill) -> dict[str, Any]:
        current_version = None
        if skill["current_version_id"]:
            current_version = self._skill_version_detail(connection, self._skill_version_row(connection, skill["current_version_id"]))
        primary_eval_set = None
        current_eval_set_version = None
        primary_row = (
            connection.execute(
                select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill["id"]).where(tables.eval_sets.c.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if primary_row is not None:
            primary_eval_set = self._eval_set_summary(connection, primary_row)
            current_eval_set_version = primary_eval_set["current_version"]
        latest_eval_run = None
        if current_version is not None and current_eval_set_version is not None:
            latest_row = (
                connection.execute(
                    select(tables.eval_runs)
                    .where(tables.eval_runs.c.skill_version_id == current_version["id"])
                    .where(tables.eval_runs.c.eval_set_version_id == current_eval_set_version["id"])
                    .where(tables.eval_runs.c.status == "finished")
                    .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            latest_eval_run = self._row_dict(latest_row) if latest_row is not None else None
        return {
            "skill": self._row_dict(skill),
            "current_version": current_version,
            "primary_eval_set": primary_eval_set,
            "latest_accepted_eval_run": latest_eval_run,
        }

    def _skill_version_detail(self, connection, version) -> dict[str, Any]:
        detail = self._row_dict(version)
        content_ref = detail.get("content_ref") or {}
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if content_ref.get("kind") == "artifact" and isinstance(locator, str) and locator.startswith("artifact:"):
            artifact_id = locator.split(":", 1)[1]
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
            if artifact is not None:
                artifact_detail = self._row_dict(artifact)
                detail["bundle_artifact"] = artifact_detail
                detail["bundle_files"] = self._bundle_files_from_artifact(artifact_detail)
        return detail

    def _eval_set_summary(self, connection, eval_set) -> dict[str, Any]:
        versions = [
            self._row_dict(row)
            for row in connection.execute(
                select(tables.eval_set_versions)
                .where(tables.eval_set_versions.c.eval_set_id == eval_set["id"])
                .order_by(desc(tables.eval_set_versions.c.version_number))
            )
            .mappings()
            .all()
        ]
        current_version = next((version for version in versions if version["id"] == eval_set["current_version_id"]), None)
        return {**self._row_dict(eval_set), "current_version": current_version, "versions": versions}

    def _eval_set_cases(self, connection, eval_set_version_id: str) -> list[dict[str, Any]]:
        memberships = (
            connection.execute(
                select(tables.eval_set_case_versions)
                .where(tables.eval_set_case_versions.c.eval_set_version_id == eval_set_version_id)
                .order_by(tables.eval_set_case_versions.c.position)
            )
            .mappings()
            .all()
        )
        cases = []
        for membership in memberships:
            case_version = self._eval_case_version_row(connection, membership["case_version_id"])
            eval_case = self._eval_case_row(connection, case_version["case_id"])
            cases.append(
                {
                    "position": membership["position"],
                    "case": self._row_dict(eval_case),
                    "case_version": self._case_version_detail(connection, case_version),
                }
            )
        return cases

    def _case_version_detail(self, connection, case_version) -> dict[str, Any]:
        input_artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == case_version["input_artifact_id"])).mappings().one()
        expected_output_artifact = (
            connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == case_version["expected_output_artifact_id"]))
            .mappings()
            .one()
        )
        return {
            **self._row_dict(case_version),
            "input_artifact": self._row_dict(input_artifact),
            "expected_output_artifact": self._row_dict(expected_output_artifact),
        }

    def _bundle_diff_from_versions(self, connection, left_version, right_version) -> dict[str, Any]:
        _left_artifact, left_files = self._bundle_artifact_for_version(connection, left_version)
        _right_artifact, right_files = self._bundle_artifact_for_version(connection, right_version)
        left_by_path = {file["path"]: file for file in left_files}
        right_by_path = {file["path"]: file for file in right_files}
        summary = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0, "binary": 0}
        files = []
        for path in sorted(set(left_by_path) | set(right_by_path)):
            left_file = left_by_path.get(path)
            right_file = right_by_path.get(path)
            if left_file is None:
                status = "added"
            elif right_file is None:
                status = "removed"
            elif left_file.get("sha256") == right_file.get("sha256"):
                status = "unchanged"
            else:
                status = "changed"
            summary[status] += 1
            if status == "unchanged":
                continue
            binary = bool((left_file or {}).get("binary") or (right_file or {}).get("binary"))
            if binary:
                summary["binary"] += 1
            diff_file = {
                "path": path,
                "status": status,
                "binary": binary,
                "left_digest": left_file.get("sha256") if left_file else None,
                "right_digest": right_file.get("sha256") if right_file else None,
                "left_size_bytes": left_file.get("size_bytes") if left_file else None,
                "right_size_bytes": right_file.get("size_bytes") if right_file else None,
            }
            left_text = left_file.get("content_text") if left_file else None
            right_text = right_file.get("content_text") if right_file else None
            if not binary and (left_text is None or isinstance(left_text, str)) and (right_text is None or isinstance(right_text, str)):
                diff_file["hunks"] = self._line_diff_hunks(left_text, right_text)
            files.append(diff_file)
        return {
            "left": self._diff_version_summary(left_version),
            "right": self._diff_version_summary(right_version),
            "summary": summary,
            "files": files,
        }

    def _bundle_artifact_for_version(self, connection, version) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        content_ref = version["content_ref"] or {}
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if content_ref.get("kind") != "artifact" or not isinstance(locator, str) or not locator.startswith("artifact:"):
            raise InvariantError(f"SkillVersion has no skill_bundle artifact to diff: {version['id']}")
        artifact_id = locator.split(":", 1)[1]
        artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
        if artifact is None:
            raise NotFoundError(f"Artifact not found: {artifact_id}")
        artifact_detail = self._row_dict(artifact)
        if artifact_detail["kind"] != "skill_bundle":
            raise InvariantError(f"SkillVersion artifact is not a skill_bundle: {version['id']}")
        files = self._bundle_files_from_artifact(artifact_detail)
        if not files:
            raise InvariantError(f"SkillVersion skill_bundle has no readable files: {version['id']}")
        return artifact_detail, files

    def _bundle_files_from_artifact(self, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        content_text = artifact.get("content_text")
        if not isinstance(content_text, str):
            return []
        try:
            manifest = json.loads(content_text)
        except json.JSONDecodeError:
            return []
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, list):
            return []
        return sorted([file for file in files if isinstance(file, dict) and isinstance(file.get("path"), str)], key=lambda file: file["path"])

    def _diff_version_summary(self, version) -> dict[str, Any]:
        return {"skill_version_id": version["id"], "version_number": version["version_number"], "content_digest": version["content_digest"]}

    def _line_diff_hunks(self, left_text: str | None, right_text: str | None) -> list[dict[str, Any]]:
        left_lines = [] if left_text is None else left_text.splitlines()
        right_lines = [] if right_text is None else right_text.splitlines()
        lines = []
        matcher = SequenceMatcher(a=left_lines, b=right_lines)
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                for offset, text in enumerate(left_lines[left_start:left_end]):
                    lines.append({"kind": "context", "old_line": left_start + offset + 1, "new_line": right_start + offset + 1, "text": text})
            if tag in {"delete", "replace"}:
                for offset, text in enumerate(left_lines[left_start:left_end]):
                    lines.append({"kind": "removed", "old_line": left_start + offset + 1, "new_line": None, "text": text})
            if tag in {"insert", "replace"}:
                for offset, text in enumerate(right_lines[right_start:right_end]):
                    lines.append({"kind": "added", "old_line": None, "new_line": right_start + offset + 1, "text": text})
        if not lines:
            return []
        return [{"old_start": 1 if left_lines else 0, "old_lines": len(left_lines), "new_start": 1 if right_lines else 0, "new_lines": len(right_lines), "lines": lines}]

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


def skill_slug_conflict(slug: str) -> FieldInvariantError:
    message = f"Skill ID 已存在：{slug}"
    return FieldInvariantError(message, [FieldError(field="slug", message=message, code="skill.slug_conflict")])
