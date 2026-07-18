from __future__ import annotations

import re

BUILDER_AGENT_ID = "skillhub-skill-builder"
BUILDER_AGENT_PROMPT = """你是 SkillHub 的 Skill 创建 Agent，负责帮助用户创建高质量的 Agent Skill。

工作方式：
- 先通过对话澄清 Skill 的使用场景、触发条件、输入输出、约束和可复用资源。
- 当用户要求创建、补充或修改 Skill 内容时，直接在当前工作目录创建或更新文本文件。
- 必须创建根目录 SKILL.md，并使用 YAML frontmatter，且只包含 name 和 description。
- name 必须是小写字母、数字和连字符，最多 64 个字符。
- description 必须说明 Skill 能力和触发场景。
- SKILL.md 正文只写对后续 Agent 真正有用的简洁指令。
- 仅在确有必要时创建 references/、scripts/ 或 assets/ 下的文本文件。
- 不要创建 README、安装指南、变更日志或与 Skill 运行无关的说明文件。
- 只写 UTF-8 文本文件，不写二进制文件。
- 不要运行命令，不要访问网络，不要依赖当前工作目录外的文件。
"""

BUILDER_TOOLS = {
    "bash": False,
    "edit": True,
    "glob": True,
    "grep": True,
    "list": True,
    "read": True,
    "write": True,
}


def safe_agent_id(value: str) -> str:
    clean = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", clean):
        raise RuntimeError(f"Unsafe Opencode agent id: {value}")
    return clean


def agent_markdown(agent: dict) -> str:
    frontmatter = {
        "description": str(agent.get("description") or ""),
        "mode": "primary",
        "model": _agent_model(agent),
        "temperature": _agent_temperature(agent.get("temperature")),
        "permission": _agent_permission(agent.get("permission")),
        "steps": list(agent.get("steps") or []),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        if value in (None, "", [], {}):
            continue
        lines.extend(_yaml_line(key, value))
    lines.extend(["---", "", str(agent.get("prompt") or "").strip(), ""])
    return "\n".join(lines)


def builder_agent_markdown() -> str:
    lines = [
        "---",
        "description: 'Create SkillHub Agent Skill bundle drafts from user requirements.'",
        "mode: primary",
        "permission:",
        "  bash: deny",
        "  edit: allow",
        "  glob: allow",
        "  grep: allow",
        "  list: allow",
        "  read: allow",
        "  write: allow",
        "---",
        "",
        BUILDER_AGENT_PROMPT.strip(),
        "",
    ]
    return "\n".join(lines)


def _agent_model(agent: dict) -> str:
    provider_id = str(agent.get("provider_id") or "").strip()
    model_id = str(agent.get("model_id") or "").strip()
    return f"{provider_id}/{model_id}" if provider_id and model_id else ""


def _agent_temperature(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _agent_permission(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, enabled in value.items():
        if isinstance(enabled, bool):
            result[str(key)] = "allow" if enabled else "deny"
    return result


def _yaml_line(key: str, value) -> list[str]:
    if isinstance(value, bool):
        return [f"{key}: {'true' if value else 'false'}"]
    if isinstance(value, (int, float)):
        return [f"{key}: {value}"]
    if isinstance(value, str):
        return [f"{key}: {value!r}"]
    if isinstance(value, list):
        return [f"{key}:", *(f"  - {str(item)!r}" for item in value)]
    if isinstance(value, dict):
        lines = [f"{key}:"]
        for item_key, item_value in value.items():
            rendered = "true" if item_value is True else "false" if item_value is False else repr(item_value)
            lines.append(f"  {item_key}: {rendered}")
        return lines
    return [f"{key}: {str(value)!r}"]
