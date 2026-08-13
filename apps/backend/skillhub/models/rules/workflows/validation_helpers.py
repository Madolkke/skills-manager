from __future__ import annotations

from collections import Counter
from typing import Any

from .json_schema import has_legacy_schema, schema_title


def issue(code: str, severity: str, message: str, selection: dict[str, str]) -> dict[str, Any]:
    return {"id": "", "code": code, "severity": severity, "message": message, "selection": selection}


def append_duplicates(items, field, missing_code, duplicate_code, label, issues, selection) -> None:
    counts = Counter(str(item.get(field, "")).strip() for item in items)
    for index, item in enumerate(items):
        value = str(item.get(field, "")).strip()
        count = counts[value]
        item_id = str(item.get("id", ""))
        located = {**selection, "itemId": item_id, "field": f"{field}.{item_id}" if item_id and field != "id" else f"{field}[{index}]"}
        if not value:
            issues.append(issue(missing_code, "error", f"{label}不能为空。", located))
        elif count > 1:
            issues.append(issue(duplicate_code, "error", f"{label}“{value}”重复。", located))


def append_optional_duplicates(items, field, code, label, issues, selection) -> None:
    counts = Counter(str(item.get(field, "")).strip() for item in items)
    for index, item in enumerate(items):
        value = str(item.get(field, "")).strip()
        count = counts[value]
        if value and count > 1:
            item_id = str(item.get("id", ""))
            issues.append(issue(code, "error", f"{label}“{value}”重复。", {**selection, "itemId": item_id, "field": f"{field}.{item_id}" if item_id else f"{field}[{index}]"}))


def append_missing_titles(items, label, issues, selection) -> None:
    for index, item in enumerate(items):
        if not str(item.get("schema", {}).get("title", "")).strip():
            item_id = str(item.get("id", ""))
            issues.append(issue("MISSING_PARAMETER_NAME", "error", f"{label}不能为空。", {**selection, "itemId": item_id, "field": f"schema.title.{item_id}" if item_id else f"schema.title[{index}]"}))


def append_legacy_schema_warnings(items, issues, selection) -> None:
    for index, item in enumerate(items):
        if has_legacy_schema(item["schema"]):
            item_id = str(item.get("id", ""))
            issues.append(issue("LEGACY_LOOSE_SCHEMA", "warning", f"字段“{schema_title(item)}”仍使用迁移后的宽松 Schema，建议补充详细结构。", {**selection, "itemId": item_id, "field": f"schema.{item_id}" if item_id else f"schema[{index}]"}))
