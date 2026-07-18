from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import ContentRef, new_id, utc_now
from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.operations.shared.results import CreateSkillVersionResult
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.schema import orm


class SkillVersionCommandMixin:
    def create_skill_version(
        self,
        *,
        skill_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
        display_name: str | None = None,
        version: str | None = None,
    ) -> CreateSkillVersionResult:
        """Legacy store facade; VersionService owns normal create-version orchestration."""
        snapshot = self.skill_version_create_snapshot(skill_id=skill_id, actor=actor)
        return self.insert_skill_version(
            skill_id=skill_id,
            content_ref=content_ref,
            change_summary=change_summary,
            display_name=display_name,
            version_number=snapshot["next_version_number"],
            version=normalize_semver(version or snapshot["next_version"]),
            actor=actor,
            make_current=make_current,
        )

    def skill_version_create_snapshot(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.version.create")
            return {
                "skill_id": skill_id,
                "next_version_number": self._next_skill_version_number(connection, skill_id),
                "next_version": self._next_skill_semver(connection, skill_id),
            }

    def insert_skill_version(
        self,
        *,
        skill_id: str,
        content_ref: ContentRef,
        change_summary: str,
        display_name: str | None,
        version_number: int,
        version: str,
        actor: str,
        make_current: bool,
    ) -> CreateSkillVersionResult:
        created_at = utc_now()
        skill_version_id = new_id("skillver")
        semver = normalize_semver(version)
        try:
            with self._write_session() as connection:
                self._skill_row(connection, skill_id)
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.version.create")
                connection.execute(
                    insert(orm.SkillVersion).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=display_name,
                        content_ref=self._content_ref_payload(content_ref),
                        content_digest=content_ref.digest,
                        change_summary=change_summary,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                if make_current:
                    connection.execute(
                        update(orm.Skill)
                        .where(orm.Skill.id == skill_id)
                        .values(current_version_id=skill_version_id, updated_at=created_at)
                    )
        except IntegrityError as exc:
            raise FieldInvariantError(
                "SkillVersion version already exists for this skill.",
                [
                    FieldError(
                        field="version",
                        message="这个 Skill 已经存在相同版本号。",
                        code="skill_version.version_conflict",
                    )
                ],
            ) from exc
        return CreateSkillVersionResult(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            version_number=version_number,
            version=semver,
        )

    def update_skill_version_name(self, *, skill_version_id: str, display_name: str | None, actor: str | None = None) -> dict[str, Any]:
        with self._write_session() as connection:
            version = self._skill_version_row(connection, skill_version_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=version["skill_id"], actor=actor, permission="skill.version.create")
            connection.execute(
                update(orm.SkillVersion)
                .where(orm.SkillVersion.id == skill_version_id)
                .values(display_name=clean_display_name(display_name))
            )
            return self._row_dict(self._skill_version_row(connection, skill_version_id))


def clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
