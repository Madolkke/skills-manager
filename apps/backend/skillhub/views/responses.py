from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from typing import Any

from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.views.schemas import (
    ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH,
    EVAL_CASE_INPUT_MAX_LENGTH,
    EVAL_CASE_NOTES_MAX_LENGTH,
    EVAL_CASE_TITLE_MAX_LENGTH,
    SAVED_VIEW_NAME_MAX_LENGTH,
    VERSION_CHANGE_SUMMARY_MAX_LENGTH,
)


def result_payload(result: Any) -> Any:
    if is_dataclass(result):
        return asdict(result)
    return result


def parse_skill_import_payload(source: dict[str, Any]):
    try:
        return parse_skill_import_source(source)
    except InvariantError as exc:
        raise skill_import_field_error(source, exc) from exc


def skill_import_field_error(source: dict[str, Any], exc: InvariantError) -> FieldInvariantError:
    detail = str(exc)
    message, code = SKILL_IMPORT_ERROR_MESSAGES.get(detail, (detail, "skill_import.invalid_bundle"))
    field = "zip_file" if source.get("kind") == "zip" else "folder_files"
    return FieldInvariantError(detail, [FieldError(field=field, message=message, code=code)])


def error_payload(exc: InvariantError) -> dict[str, Any]:
    content: dict[str, Any] = {"detail": str(exc)}
    field_errors = [error.to_payload() for error in getattr(exc, "field_errors", [])]
    if field_errors:
        content["field_errors"] = field_errors
    return content


def request_validation_field_errors(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    field_errors = []
    for error in errors:
        field = request_body_field(error.get("loc", ()))
        if not field:
            continue
        field_errors.append(
            {
                "field": field,
                "message": request_validation_message(field, str(error.get("type", "invalid"))),
                "code": f"request.{error.get('type', 'invalid')}",
            }
        )
    return field_errors or [{"field": "_form", "message": "请求字段不完整或格式不正确。", "code": "request.invalid"}]


def request_body_field(location: Any) -> str:
    parts: list[str] = []
    for part in location:
        if part == "body":
            continue
        if isinstance(part, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{part}]"
            continue
        parts.append(str(part))
    return ".".join(parts)


def request_validation_message(field: str, error_type: str) -> str:
    batch_message = batch_case_validation_message(field, error_type)
    if batch_message:
        return batch_message
    eval_case_message = eval_case_validation_message(field, error_type)
    if eval_case_message:
        return eval_case_message
    label = API_FIELD_LABELS.get(field, field)
    if error_type == "missing":
        return f"填写 {label}"
    if field == "slug" and error_type in {"string_pattern_mismatch", "string_too_long", "string_too_short"}:
        return "Skill ID 只能使用小写字母、数字和连字符，且必须以字母或数字开头，最多 64 个字符。"
    if field == "environment_tags" and error_type in {"string_pattern_mismatch", "string_too_long", "string_too_short"}:
        return "运行环境标签只能使用字母、数字、点、下划线和连字符，每个最多 64 个字符。"
    if field == "owner_ref" and error_type in {"string_pattern_mismatch", "string_too_long", "string_too_short"}:
        return "归属只能使用字母、数字、点、下划线、@ 和连字符，最多 120 个字符。"
    if field == "subject_id" and error_type in {"string_pattern_mismatch", "string_too_long", "string_too_short"}:
        return "成员只能使用字母、数字、点、下划线、@ 和连字符，最多 120 个字符。"
    if field == "name" and error_type == "string_too_long":
        return f"保存视图名称最多 {SAVED_VIEW_NAME_MAX_LENGTH} 个字符。"
    if field == "name" and error_type in {"missing", "string_too_short"}:
        return "填写保存视图名称。"
    if field == "note" and error_type == "string_too_long":
        return f"验证说明最多 {ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH} 个字符。"
    if field == "change_summary" and error_type == "string_too_long":
        return f"版本说明最多 {VERSION_CHANGE_SUMMARY_MAX_LENGTH} 个字符。"
    return f"{label} 格式不正确。"


def batch_case_validation_message(field: str, error_type: str) -> str | None:
    match = re.fullmatch(r"cases\[(\d+)]\.(\w+)", field)
    if not match:
        return None
    row_number = int(match.group(1)) + 1
    field_name = match.group(2)
    label = EVAL_CASE_FIELD_LABELS.get(field_name, field_name)
    if error_type == "string_too_long" and field_name in EVAL_CASE_FIELD_MAX_LENGTHS:
        return f"第 {row_number} 行{prefixed_limit_phrase(label, EVAL_CASE_FIELD_MAX_LENGTHS[field_name])}"
    if error_type in {"missing", "string_too_short"}:
        return f"第 {row_number} 行填写{prefixed_label(label)}。"
    return f"第 {row_number} 行 {label} 格式不正确。"


def eval_case_validation_message(field: str, error_type: str) -> str | None:
    if field not in EVAL_CASE_FIELD_LABELS:
        return None
    label = EVAL_CASE_FIELD_LABELS[field]
    if error_type == "string_too_long":
        return limit_phrase(label, EVAL_CASE_FIELD_MAX_LENGTHS[field])
    if error_type in {"missing", "string_too_short"}:
        return f"填写{prefixed_label(label)}。"
    return None


def limit_phrase(label: str, max_length: int) -> str:
    return f"{label} 最多 {max_length} 个字符。" if label.isascii() else f"{label}最多 {max_length} 个字符。"


def prefixed_limit_phrase(label: str, max_length: int) -> str:
    return f" {limit_phrase(label, max_length)}" if label.isascii() else limit_phrase(label, max_length)


def prefixed_label(label: str) -> str:
    return f" {label}" if label.isascii() else label


EVAL_CASE_FIELD_LABELS = {
    "title": "标题",
    "steps": "测试步骤",
    "input": "步骤输入",
    "workspace_base64": "工作目录压缩包",
    "notes": "备注",
}

EVAL_CASE_FIELD_MAX_LENGTHS = {
    "title": EVAL_CASE_TITLE_MAX_LENGTH,
    "input": EVAL_CASE_INPUT_MAX_LENGTH,
    "notes": EVAL_CASE_NOTES_MAX_LENGTH,
}

API_FIELD_LABELS = {
    "slug": "Skill ID",
    "owner_ref": "归属",
    "skill_version_id": "SkillVersion",
    "eval_set_id": "测评集",
    "environment_tags": "运行环境标签",
    "change_summary": "版本说明",
    "name": "保存视图名称",
    "note": "验证说明",
    "subject_id": "成员",
}

SKILL_IMPORT_ERROR_MESSAGES = {
    "Skill bundle must contain SKILL.md at its root.": ("选择的 Skill bundle 根目录必须包含 SKILL.md。", "skill_import.skill_md_missing"),
    "SKILL.md must be UTF-8 text.": ("SKILL.md 必须是 UTF-8 文本。", "skill_import.skill_md_not_utf8"),
    "SKILL.md must start with YAML frontmatter.": ("SKILL.md 必须以 YAML frontmatter 开头。", "skill_import.frontmatter_missing"),
    "SKILL.md frontmatter cannot be empty.": ("SKILL.md frontmatter 不能是空的。", "skill_import.frontmatter_empty"),
    "SKILL.md frontmatter must end with ---.": ("SKILL.md frontmatter 必须用 --- 结束。", "skill_import.frontmatter_unclosed"),
    "Skill name must be lowercase letters, numbers, and hyphens, up to 64 characters.": (
        "SKILL.md frontmatter name 只能使用小写字母、数字和连字符，且必须以字母或数字开头，最多 64 个字符。",
        "skill_import.name_invalid",
    ),
    "Skill description is required.": ("SKILL.md frontmatter 需要 description。", "skill_import.description_required"),
    "Skill description must be 1024 characters or fewer.": ("SKILL.md frontmatter description 最多 1024 个字符。", "skill_import.description_too_long"),
    "Skill import zip is not readable.": ("选择的 zip 不是可读取的 Skill bundle。", "skill_import.zip_unreadable"),
}
