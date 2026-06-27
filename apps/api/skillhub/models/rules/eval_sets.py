from __future__ import annotations

from skillhub.models.errors import FieldError, FieldInvariantError


def normalize_eval_set_name(value: str | None) -> str:
    clean = (value or "").strip()
    if not clean:
        raise FieldInvariantError(
            "Eval set name is required.",
            [FieldError(field="name", message="填写测评集名称。", code="eval_set.name_required")],
        )
    if len(clean) > 120:
        raise FieldInvariantError(
            "Eval set name is too long.",
            [FieldError(field="name", message="测评集名称最多 120 个字符。", code="eval_set.name_too_long")],
        )
    return clean


def normalize_eval_set_description(value: str | None) -> str:
    return (value or "").strip()


def eval_set_name_conflict(name: str) -> FieldInvariantError:
    return FieldInvariantError(
        "Eval set name already exists for this skill.",
        [FieldError(field="name", message=f"测评集名称“{name}”已存在。", code="eval_set.name_conflict")],
    )
