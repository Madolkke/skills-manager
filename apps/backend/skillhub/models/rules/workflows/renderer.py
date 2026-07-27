from __future__ import annotations

from typing import Any

from .generators.rendering import (
    append_calls,
    append_metadata,
    append_paragraph,
    append_parameters,
    append_roles,
    append_script,
    append_transitions,
    frontmatter_lines,
)

GENERATOR_VERSION = "workflow-skill-v3"


def render_skill_markdown(*, slug: str, document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    metadata = workflow["metadata"]
    definitions = {(item["id"], item["revision"]): item for item in document.get("collectionSnapshots", [])}
    nodes = workflow["nodes"]
    node_names = {item["id"]: item["name"] for item in nodes}
    roles = {item["id"]: item for item in workflow["deviceRoles"]}
    lines = [*frontmatter_lines(slug, metadata), "", f"# {metadata['name'] or slug}", ""]
    append_paragraph(lines, metadata["description"])
    append_metadata(lines, metadata)
    append_parameters(lines, "全局输入", workflow["inputs"])
    append_roles(lines, workflow["deviceRoles"])

    steps = [item for item in nodes if "stepType" in item]
    lines.extend(["## 排查步骤", ""])
    for index, step in enumerate(steps, start=1):
        lines.extend([f"### {index}. {step['name']}", ""])
        lines.append(f"- 起始步骤: {'是' if step['isStart'] else '否'}")
        lines.append(f"- 类型: {'脚本草稿' if step['stepType'] == 'script' else '条件表达式'}")
        lines.append("")
        append_paragraph(lines, step["description"])
        append_calls(
            lines,
            step["collectionCalls"],
            definitions,
            roles,
            workflow_inputs={item["id"]: item for item in workflow["inputs"]},
        )
        append_transitions(lines, step["topology"], node_names)
        append_script(lines, step)

    conclusions = [item for item in nodes if item.get("nodeType") == "conclusion"]
    lines.extend(["## 排查结论", ""])
    for conclusion in conclusions:
        lines.extend([f"### {conclusion['name']}", ""])
        lines.append(f"- 故障根因: {conclusion['rootCause'] or '未填写'}")
        lines.append(f"- 修复建议: {conclusion['repairRecommendation'] or '未填写'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
