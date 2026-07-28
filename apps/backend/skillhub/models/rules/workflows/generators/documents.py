from __future__ import annotations

from hashlib import sha256
from typing import Any

from .rendering import (
    append_calls,
    append_metadata,
    append_paragraph,
    append_parameters,
    append_roles,
    append_schema_children,
    append_script,
    append_transitions,
    frontmatter_lines,
    schema_type,
)


def node_reference_path(node: dict[str, Any]) -> str:
    kind = "step" if "stepType" in node else "conclusion"
    return f"references/{kind}-{_stable_hash(node['id'])}.md"


def collection_reference_path(definition: dict[str, Any]) -> str:
    identity = f"{definition['id']}@{definition['revision']}"
    return f"references/collection-{_stable_hash(identity)}.md"


def render_entry(*, slug: str, document: dict[str, Any], reference_path: str, split_nodes: bool) -> str:
    metadata = document["workflow"]["metadata"]
    lines = [*frontmatter_lines(slug, metadata), "", f"# {metadata['name'] or slug}", ""]
    append_paragraph(lines, metadata["description"])
    lines.extend(
        [
            "## 操作协议",
            "",
            "1. 先读取工作流参考文件，确认全局输入、设备角色、起始步骤和跳转条件。",
            "2. 执行节点所列采集命令时，按参数绑定填充值，并保留输出字段供后续判断。",
            "3. 按跳转条件推进，命中结论后输出故障根因与修复建议。",
            "4. 脚本内容仅作为草稿，执行前必须结合目标环境复核。",
            "",
            "## 参考文件",
            "",
        ]
    )
    label = "节点与 Collection 索引" if split_nodes else "完整工作流"
    lines.append(f"- [{label}]({reference_path})")
    if not split_nodes:
        lines.append("- [Collection 定义与调用](references/collections.md)")
    lines.append("")
    return _finish(lines)


def render_workflow_reference(document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    metadata = workflow["metadata"]
    nodes = workflow["nodes"]
    node_names = {item["id"]: item["name"] for item in nodes}
    lines = [f"# {metadata['name']}：完整工作流", ""]
    append_paragraph(lines, metadata["description"])
    append_metadata(lines, metadata)
    append_parameters(lines, "全局输入", workflow["inputs"])
    append_roles(lines, workflow["deviceRoles"])
    lines.extend(["## 排查步骤", ""])
    for index, step in enumerate((item for item in nodes if "stepType" in item), start=1):
        lines.extend([f"### {index}. {step['name']}", ""])
        _append_step_summary(lines, step)
        append_transitions(lines, step["topology"], node_names)
        append_script(lines, step, include_options=True)
    lines.extend(["## 排查结论", ""])
    for conclusion in (item for item in nodes if item.get("nodeType") == "conclusion"):
        _append_conclusion(lines, conclusion, level=3)
    return _finish(lines)


def render_collections_reference(document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    definitions = _definitions(document)
    roles = {item["id"]: item for item in workflow["deviceRoles"]}
    workflow_inputs = {item["id"]: item for item in workflow["inputs"]}
    lines = ["# Collection 定义与调用", "", "## Collection 定义", ""]
    if not definitions:
        lines.extend(["当前工作流没有 Collection 定义。", ""])
    for definition in definitions.values():
        append_collection_definition(lines, definition, level=3)
    lines.extend(["## 工作流中的采集调用", ""])
    called = False
    for step in (item for item in workflow["nodes"] if "stepType" in item):
        if not step["collectionCalls"]:
            continue
        called = True
        lines.extend([f"### {step['name']}", ""])
        append_calls(lines, step["collectionCalls"], definitions, roles, workflow_inputs=workflow_inputs)
    if not called:
        lines.extend(["当前工作流没有采集调用。", ""])
    return _finish(lines)


def render_node_index(document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    metadata = workflow["metadata"]
    definitions = _definitions(document)
    lines = [f"# {metadata['name']}：节点索引", ""]
    append_paragraph(lines, metadata["description"])
    append_metadata(lines, metadata)
    append_parameters(lines, "全局输入", workflow["inputs"])
    append_roles(lines, workflow["deviceRoles"])
    lines.extend(["## 节点", ""])
    for index, node in enumerate(workflow["nodes"], start=1):
        kind = "步骤" if "stepType" in node else "结论"
        lines.append(f"- [{index}. {node['name']}（{kind}）]({node_reference_path(node).removeprefix('references/')})")
    lines.extend(["", "## Collection", ""])
    if definitions:
        for definition in definitions.values():
            path = collection_reference_path(definition).removeprefix("references/")
            lines.append(f"- [{definition['metadata']['name']} (`{definition['key']}`)]({path})")
    else:
        lines.append("当前工作流没有 Collection 定义。")
    lines.append("")
    return _finish(lines)


def render_node_reference(document: dict[str, Any], node: dict[str, Any]) -> str:
    if "stepType" not in node:
        lines = [f"# 结论：{node['name']}", ""]
        _append_conclusion(lines, node, level=2, include_heading=False)
        return _finish(lines)
    workflow = document["workflow"]
    definitions = _definitions(document)
    roles = {item["id"]: item for item in workflow["deviceRoles"]}
    workflow_inputs = {item["id"]: item for item in workflow["inputs"]}
    node_names = {item["id"]: item["name"] for item in workflow["nodes"]}
    lines = [f"# 步骤：{node['name']}", ""]
    _append_step_summary(lines, node)
    append_calls(
        lines,
        node["collectionCalls"],
        definitions,
        roles,
        workflow_inputs=workflow_inputs,
        level=2,
        collection_link=lambda definition: collection_reference_path(definition).removeprefix("references/"),
    )
    append_transitions(lines, node["topology"], node_names, level=2)
    append_script(lines, node, level=2, include_options=True)
    return _finish(lines)


def render_collection_reference(definition: dict[str, Any]) -> str:
    lines: list[str] = []
    append_collection_definition(lines, definition, level=1)
    return _finish(lines)


def append_collection_definition(lines: list[str], definition: dict[str, Any], *, level: int) -> None:
    metadata = definition["metadata"]
    lines.extend([f"{'#' * level} {metadata['name'] or definition['key']}", ""])
    lines.extend([f"- Collection key: `{definition['key']}`", f"- 版本: {definition['revision']}"])
    if definition.get("forkedFrom"):
        fork = definition["forkedFrom"]
        lines.append(f"- 派生自: `{fork['id']}@{fork['revision']}`")
    for label, value in (
        ("产业", metadata["industry"]),
        ("设备", metadata["device"]),
        ("适用版本", "、".join(metadata["versions"])),
        ("标签", "、".join(metadata["tags"])),
    ):
        if value:
            lines.append(f"- {label}: {value}")
    lines.append("")
    append_paragraph(lines, metadata["description"])
    command = definition["spec"]["commandTemplate"]
    if command:
        lines.extend([f"{'#' * (level + 1)} 采集命令", "", "```text", command.rstrip(), "```", ""])
    append_parameters(lines, "输入参数", definition["inputs"], level=level + 1)
    if definition["outputs"]:
        lines.extend([f"{'#' * (level + 1)} 输出字段", ""])
        for output in definition["outputs"]:
            schema = output["schema"]
            required = "必填" if output["required"] else "可选"
            title = schema.get("title") or output["key"]
            description = f" - {schema['description']}" if schema.get("description") else ""
            lines.append(f"- `{output['key']}` ({schema_type(schema)}, {required}): {title}{description}")
            append_schema_children(lines, schema, indent="  ")
        lines.append("")
    samples = [sample["name"] for sample in definition["spec"]["outputSamples"] if sample["name"].strip()]
    if samples:
        lines.extend([f"{'#' * (level + 1)} 回显示例", ""])
        lines.extend(f"- {name}" for name in samples)
        lines.append("")


def _append_step_summary(lines: list[str], step: dict[str, Any]) -> None:
    lines.append(f"- 起始步骤: {'是' if step['isStart'] else '否'}")
    lines.append(f"- 类型: {'脚本草稿' if step['stepType'] == 'script' else '条件表达式'}")
    lines.append("")
    append_paragraph(lines, step["description"])


def _append_conclusion(lines: list[str], conclusion: dict[str, Any], *, level: int, include_heading: bool = True) -> None:
    if include_heading:
        lines.extend([f"{'#' * level} {conclusion['name']}", ""])
    lines.append(f"- 故障根因: {conclusion['rootCause'] or '未填写'}")
    lines.append(f"- 修复建议: {conclusion['repairRecommendation'] or '未填写'}")
    lines.append("")


def _definitions(document: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(item["id"], item["revision"]): item for item in document.get("collectionSnapshots", [])}


def _stable_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _finish(lines: list[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"
