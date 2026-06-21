from __future__ import annotations

import json
from typing import Any


MAX_TOOL_OUTPUT_PREVIEW = 2_000


def compact_message_output(response: object) -> str:
    trace = extract_opencode_trace(response)
    if trace["text_output"].strip():
        return trace["text_output"].strip()
    if not trace["recognized"]:
        text = _find_text(response)
        if text.strip():
            return text.strip()
    try:
        return json.dumps(response, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(response)


def extract_opencode_trace(response: object) -> dict[str, Any]:
    state = {
        "recognized": False,
        "reasoning": [],
        "texts": [],
        "tool_calls": [],
        "finish": "",
        "model_id": "",
        "provider_id": "",
    }
    _collect_trace(response, state, role=None)
    return {
        "recognized": bool(state["recognized"]),
        "reasoning_text": "\n".join(part for part in state["reasoning"] if part).strip(),
        "tool_calls": state["tool_calls"],
        "text_output": "\n".join(part for part in state["texts"] if part).strip(),
        "finish": state["finish"],
        "model_id": state["model_id"],
        "provider_id": state["provider_id"],
    }


def _collect_trace(value: object, state: dict[str, Any], *, role: str | None) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_trace(item, state, role=role)
        return
    if not isinstance(value, dict):
        return

    if isinstance(value.get("data"), list):
        state["recognized"] = True
        _collect_trace(value["data"], state, role=role)
        return

    current_role = _opencode_message_role(value) or role
    _capture_message_metadata(value, state)

    parts = value.get("parts")
    if isinstance(parts, list):
        state["recognized"] = True
        if current_role and current_role != "assistant":
            return
        _collect_trace(parts, state, role="assistant")
        return

    content = value.get("content")
    if isinstance(content, list):
        state["recognized"] = True
        if current_role and current_role != "assistant":
            return
        _collect_trace(content, state, role="assistant")
        return

    part_type = value.get("type")
    if not isinstance(part_type, str):
        return
    state["recognized"] = True
    if part_type == "text":
        text = value.get("text")
        if isinstance(text, str):
            state["texts"].append(text)
    elif part_type == "reasoning":
        text = value.get("text")
        if isinstance(text, str):
            state["reasoning"].append(text)
    elif part_type == "tool":
        state["tool_calls"].append(_tool_call(value))


def _opencode_message_role(value: dict[str, Any]) -> str | None:
    role = value.get("role")
    if isinstance(role, str):
        return role
    info = value.get("info")
    if isinstance(info, dict) and isinstance(info.get("role"), str):
        return info["role"]
    message_type = value.get("type")
    if message_type in {"assistant", "user"}:
        return str(message_type)
    return None


def _capture_message_metadata(value: dict[str, Any], state: dict[str, Any]) -> None:
    info = value.get("info") if isinstance(value.get("info"), dict) else value
    if not isinstance(info, dict):
        return
    finish = info.get("finish")
    if isinstance(finish, str):
        state["finish"] = finish
    provider_id = info.get("providerID")
    if isinstance(provider_id, str):
        state["provider_id"] = provider_id
    model_id = info.get("modelID")
    if isinstance(model_id, str):
        state["model_id"] = model_id
    model = info.get("model")
    if isinstance(model, dict):
        provider = model.get("providerID")
        model_value = model.get("id") or model.get("modelID")
        if isinstance(provider, str):
            state["provider_id"] = provider
        if isinstance(model_value, str):
            state["model_id"] = model_value


def _tool_call(part: dict[str, Any]) -> dict[str, Any]:
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    input_value = state.get("input") if isinstance(state, dict) else None
    output_value = state.get("output") if isinstance(state, dict) else None
    status = state.get("status") if isinstance(state, dict) else None
    tool = part.get("tool") or part.get("name") or ""
    call_id = part.get("callID") or part.get("call_id") or part.get("id") or ""
    return {
        "tool": str(tool),
        "status": str(status or ""),
        "input": input_value if input_value is not None else {},
        "output_preview": _preview(output_value),
        "call_id": str(call_id),
    }


def _preview(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            text = str(value)
    return text[:MAX_TOOL_OUTPUT_PREVIEW]


def _find_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := _find_text(item)).strip())
    if not isinstance(value, dict):
        return ""
    for key in ("text", "content", "message", "output"):
        part = _find_text(value.get(key))
        if part.strip():
            return part
    if "parts" in value:
        return _find_text(value["parts"])
    return ""
