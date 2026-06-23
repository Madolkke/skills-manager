from __future__ import annotations

from skillhub.domain.errors import FieldError, FieldInvariantError


def skill_slug_conflict(slug: str, owner_ref: str | None = None) -> FieldInvariantError:
    message = f"该用户下 Skill ID 已存在：{slug}" if owner_ref else f"Skill ID 已存在：{slug}"
    return FieldInvariantError(message, [FieldError(field="slug", message=message, code="skill.slug_conflict")])
