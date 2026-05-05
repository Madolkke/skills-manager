from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, insert, select, update

from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.domain.models import ContentRef, digest_text, new_id, normalize_tags, utc_now
from skillhub.infrastructure.db import tables


@dataclass(frozen=True)
class CreateSkillResult:
    skill_id: str
    eval_set_id: str
    eval_set_version_id: str
    tag_set_id: str
    variant_id: str
    variant_version_id: str


@dataclass(frozen=True)
class CreateVariantVersionResult:
    skill_id: str
    variant_id: str
    variant_version_id: str
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


class SqlSkillRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        variant_name: str,
        variant_label: str,
        variant_summary: str,
        tags: list[str],
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
    ) -> CreateSkillResult:
        normalized_tags = normalize_tags(tags)
        normalized_hash = digest_text("\n".join(normalized_tags))
        created_at = utc_now()
        skill_id = new_id("skill")
        eval_set_id = new_id("evalset")
        eval_set_version_id = new_id("evalsetver")
        variant_id = new_id("variant")
        variant_version_id = new_id("varver")

        with self.engine.begin() as connection:
            tag_set_id = self._get_or_create_tag_set(
                connection,
                tags=normalized_tags,
                normalized_hash=normalized_hash,
                created_at=created_at,
            )

            connection.execute(
                insert(tables.skills).values(
                    id=skill_id,
                    slug=slug,
                    owner_ref=owner_ref,
                    default_variant_id=None,
                    lifecycle_status="active",
                    created_at=created_at,
                    updated_at=created_at,
                )
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
            connection.execute(
                insert(tables.variants).values(
                    id=variant_id,
                    skill_id=skill_id,
                    name=variant_name,
                    label=variant_label,
                    summary=variant_summary,
                    tag_set_id=tag_set_id,
                    current_version_id=None,
                    lifecycle_status="active",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(tables.variant_versions).values(
                    id=variant_version_id,
                    skill_id=skill_id,
                    variant_id=variant_id,
                    version_number=1,
                    content_ref=self._content_ref_payload(content_ref),
                    content_digest=content_ref.digest,
                    change_summary=change_summary,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                update(tables.variants)
                .where(tables.variants.c.id == variant_id)
                .values(current_version_id=variant_version_id, updated_at=created_at)
            )
            connection.execute(
                update(tables.skills)
                .where(tables.skills.c.id == skill_id)
                .values(default_variant_id=variant_id, updated_at=created_at)
            )

        return CreateSkillResult(
            skill_id=skill_id,
            eval_set_id=eval_set_id,
            eval_set_version_id=eval_set_version_id,
            tag_set_id=tag_set_id,
            variant_id=variant_id,
            variant_version_id=variant_version_id,
        )

    def create_variant_version(
        self,
        *,
        variant_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
    ) -> CreateVariantVersionResult:
        created_at = utc_now()
        variant_version_id = new_id("varver")

        with self.engine.begin() as connection:
            variant = self._variant_row(connection, variant_id)
            version_number = self._next_variant_version_number(connection, variant_id)
            connection.execute(
                insert(tables.variant_versions).values(
                    id=variant_version_id,
                    skill_id=variant["skill_id"],
                    variant_id=variant_id,
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
                    update(tables.variants)
                    .where(tables.variants.c.id == variant_id)
                    .values(current_version_id=variant_version_id, updated_at=created_at)
                )

        return CreateVariantVersionResult(
            skill_id=variant["skill_id"],
            variant_id=variant_id,
            variant_version_id=variant_version_id,
            version_number=version_number,
        )

    def promote_variant_version(self, *, variant_id: str, version_id: str) -> None:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            variant = self._variant_row(connection, variant_id)
            version = self._variant_version_row(connection, version_id)
            if version["variant_id"] != variant_id:
                raise InvariantError("Variant current_version_id must point to its own version.")
            connection.execute(
                update(tables.variants)
                .where(tables.variants.c.id == variant_id)
                .values(current_version_id=version_id, updated_at=updated_at)
            )

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
                connection,
                kind="eval_input",
                namespace=skill_id,
                content=input_text,
                actor=actor,
                created_at=created_at,
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
            skill_id=skill_id,
            eval_set_id=eval_set["id"],
            eval_set_version_id=eval_set_version_id,
            eval_case_id=eval_case_id,
            eval_case_version_id=eval_case_version_id,
            input_artifact_id=input_artifact_id,
            expected_output_artifact_id=expected_output_artifact_id,
        )

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
                connection,
                kind="eval_input",
                namespace=skill_id,
                content=input_text,
                actor=actor,
                created_at=created_at,
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
                        if self._eval_case_version_row(connection, case_version_id)["case_id"] == case_id
                        else case_version_id
                        for case_version_id in self._eval_set_case_version_ids(connection, current_eval_set_version["id"])
                    ],
                    created_at=created_at,
                    actor=actor,
                )

        return CreateEvalCaseResult(
            skill_id=skill_id,
            eval_set_id=eval_set["id"],
            eval_set_version_id=eval_set_version_id,
            eval_case_id=case_id,
            eval_case_version_id=eval_case_version_id,
            input_artifact_id=input_artifact_id,
            expected_output_artifact_id=expected_output_artifact_id,
        )

    def _get_or_create_tag_set(
        self,
        connection,
        *,
        tags: tuple[str, ...],
        normalized_hash: str,
        created_at: datetime,
    ) -> str:
        existing = connection.execute(
            select(tables.tag_sets.c.id).where(tables.tag_sets.c.normalized_hash == normalized_hash)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        tag_set_id = new_id("tagset")
        connection.execute(
            insert(tables.tag_sets).values(
                id=tag_set_id,
                tags=list(tags),
                normalized_hash=normalized_hash,
                created_at=created_at,
            )
        )
        return tag_set_id

    def _variant_row(self, connection, variant_id: str):
        row = (
            connection.execute(select(tables.variants).where(tables.variants.c.id == variant_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"Variant not found: {variant_id}")
        return row

    def _variant_version_row(self, connection, version_id: str):
        row = (
            connection.execute(select(tables.variant_versions).where(tables.variant_versions.c.id == version_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"VariantVersion not found: {version_id}")
        return row

    def _eval_case_row(self, connection, case_id: str):
        row = (
            connection.execute(select(tables.eval_cases).where(tables.eval_cases.c.id == case_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"EvalCase not found: {case_id}")
        return row

    def _eval_case_version_row(self, connection, case_version_id: str):
        row = (
            connection.execute(select(tables.eval_case_versions).where(tables.eval_case_versions.c.id == case_version_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"EvalCaseVersion not found: {case_version_id}")
        return row

    def _primary_eval_set_row(self, connection, skill_id: str):
        row = (
            connection.execute(
                select(tables.eval_sets)
                .where(tables.eval_sets.c.skill_id == skill_id)
                .where(tables.eval_sets.c.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"Primary EvalSet not found for skill: {skill_id}")
        return row

    def _eval_set_version_row(self, connection, eval_set_version_id: str):
        row = (
            connection.execute(select(tables.eval_set_versions).where(tables.eval_set_versions.c.id == eval_set_version_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"EvalSetVersion not found: {eval_set_version_id}")
        return row

    def _next_variant_version_number(self, connection, variant_id: str) -> int:
        version_numbers = connection.execute(
            select(tables.variant_versions.c.version_number).where(tables.variant_versions.c.variant_id == variant_id)
        ).scalars()
        return 1 + max(version_numbers, default=0)

    def _next_eval_case_version_number(self, connection, case_id: str) -> int:
        version_numbers = connection.execute(
            select(tables.eval_case_versions.c.version_number).where(tables.eval_case_versions.c.case_id == case_id)
        ).scalars()
        return 1 + max(version_numbers, default=0)

    def _next_eval_set_version_number(self, connection, eval_set_id: str) -> int:
        version_numbers = connection.execute(
            select(tables.eval_set_versions.c.version_number).where(tables.eval_set_versions.c.eval_set_id == eval_set_id)
        ).scalars()
        return 1 + max(version_numbers, default=0)

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
        connection.execute(
            insert(tables.eval_set_case_versions),
            [
                {
                    "eval_set_version_id": eval_set_version_id,
                    "skill_id": skill_id,
                    "case_version_id": case_version_id,
                    "position": position,
                }
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
        artifact_id = new_id("artifact")
        content_digest = digest_text(content)
        connection.execute(
            insert(tables.artifacts).values(
                id=artifact_id,
                kind=kind,
                namespace=namespace,
                locator=f"inline:{content_digest}",
                digest=content_digest,
                media_type="text/plain",
                size_bytes=len(content.encode("utf-8")),
                created_at=created_at,
                created_by=actor,
            )
        )
        return artifact_id

    def _content_ref_payload(self, content_ref: ContentRef) -> dict[str, str]:
        payload = {
            "kind": content_ref.kind,
            "locator": content_ref.locator,
            "digest": content_ref.digest,
        }
        if content_ref.path is not None:
            payload["path"] = content_ref.path
        return payload
