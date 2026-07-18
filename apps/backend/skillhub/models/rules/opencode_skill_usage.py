from __future__ import annotations

import json
from typing import Any

SKILL_TOOL_NAMES = {"skill"}
COMPLETED_STATUSES = {"completed", "complete", "success", "succeeded"}


def skill_usage_evidence(tool_calls: list[dict[str, Any]], skill_slug: str) -> dict[str, Any]:
    slug = skill_slug.strip()
    matches = [_skill_call_evidence(call, slug) for call in tool_calls if _matches_skill_call(call, slug)]
    return {
        "skill_slug": slug,
        "used": bool(matches),
        "count": len(matches),
        "calls": matches,
    }


def other_skill_usage_evidence(tool_calls: list[dict[str, Any]], allowed_skill_slug: str) -> dict[str, Any]:
    allowed = allowed_skill_slug.strip()
    matches = [
        _skill_call_evidence(call, allowed)
        for call in tool_calls
        if _is_completed_skill_tool_call(call) and _called_skill_name(call) != allowed
    ]
    return {
        "allowed_skill_slug": allowed,
        "used_other_skill": bool(matches),
        "count": len(matches),
        "calls": matches,
    }


def _matches_skill_call(call: dict[str, Any], skill_slug: str) -> bool:
    if not skill_slug:
        return False
    return _is_completed_skill_tool_call(call) and _called_skill_name(call) == skill_slug


def _skill_call_evidence(call: dict[str, Any], skill_slug: str) -> dict[str, Any]:
    return {
        "tool": str(call.get("tool") or ""),
        "status": str(call.get("status") or ""),
        "call_id": str(call.get("call_id") or ""),
        "matched_skill_slug": skill_slug,
        "called_skill_name": _called_skill_name(call),
        "input_preview": _preview(call.get("input")),
        "metadata": call.get("metadata") if isinstance(call.get("metadata"), dict) else {},
        "output_preview": str(call.get("output_preview") or ""),
    }


def _is_completed_skill_tool_call(call: dict[str, Any]) -> bool:
    tool = str(call.get("tool") or "").strip().lower()
    if tool not in SKILL_TOOL_NAMES:
        return False
    status = str(call.get("status") or "").strip().lower()
    return status in COMPLETED_STATUSES


def _called_skill_name(call: dict[str, Any]) -> str:
    input_value = call.get("input")
    if isinstance(input_value, dict):
        for key in ("name", "skill", "skill_slug", "slug"):
            value = input_value.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    metadata = call.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _preview(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)
