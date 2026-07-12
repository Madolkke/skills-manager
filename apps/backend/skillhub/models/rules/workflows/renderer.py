from __future__ import annotations

import json
from typing import Any

import yaml


GENERATOR_VERSION = "workflow-skill-v2"


def render_skill_markdown(*, slug: str, document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    metadata = workflow["metadata"]
    definitions = {(item["id"], item["revision"]): item for item in document.get("collectionSnapshots", [])}
    nodes = workflow["nodes"]
    node_names = {item["id"]: item["name"] for item in nodes}
    roles = {item["id"]: item for item in workflow["deviceRoles"]}
    frontmatter = yaml.safe_dump(
        {"name": slug, "description": metadata["description"]},
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).strip()
    lines = ["---", frontmatter, "---", "", f"# {metadata['name'] or slug}", ""]
    _paragraph(lines, metadata["description"])
    _metadata(lines, metadata)
    _parameters(lines, "全局输入", workflow["inputs"])
    _roles(lines, workflow["deviceRoles"])

    steps = [item for item in nodes if "stepType" in item]
    lines.extend(["## 排查步骤", ""])
    for index, step in enumerate(steps, start=1):
        lines.extend([f"### {index}. {step['name']}", ""])
        lines.append(f"- 起始步骤: {'是' if step['isStart'] else '否'}")
        lines.append(f"- 类型: {'脚本草稿' if step['stepType'] == 'script' else '条件表达式'}")
        lines.append("")
        _paragraph(lines, step["description"])
        _parameters(lines, "步骤输入", [item["parameter"] for item in step["inputs"]])
        _calls(
            lines,
            step["collectionCalls"],
            definitions,
            roles,
            workflow_inputs={item["id"]: item for item in workflow["inputs"]},
            step_inputs={item["parameter"]["id"]: item["parameter"] for item in step["inputs"]},
        )
        _transitions(lines, step["topology"], node_names)
        if step["stepType"] == "script" and step.get("script", {}).get("source", "").strip():
            script = step["script"]
            lines.extend(["#### 脚本草稿", "", f"```{script.get('language') or 'text'}", script["source"].rstrip(), "```", ""])

    conclusions = [item for item in nodes if item.get("nodeType") == "conclusion"]
    lines.extend(["## 排查结论", ""])
    for conclusion in conclusions:
        lines.extend([f"### {conclusion['name']}", ""])
        lines.append(f"- 故障根因: {conclusion['rootCause'] or '未填写'}")
        lines.append(f"- 修复建议: {conclusion['repairRecommendation'] or '未填写'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _metadata(lines: list[str], metadata: dict[str, Any]) -> None:
    values = [
        ("工作流编码", metadata["code"]),
        ("产业", metadata["industry"]),
        ("设备", metadata["device"]),
        ("适用版本", "、".join(metadata["versions"])),
    ]
    if any(value for _, value in values):
        lines.extend(["## 工作流信息", ""])
        lines.extend(f"- {label}: {value}" for label, value in values if value)
        lines.append("")


def _parameters(lines: list[str], heading: str, parameters: list[dict[str, Any]]) -> None:
    if not parameters:
        return
    lines.extend([f"## {heading}" if heading == "全局输入" else f"#### {heading}", ""])
    for item in parameters:
        required = "必填" if item["required"] else "可选"
        description = f" - {item['description']}" if item["description"] else ""
        lines.append(f"- `{item['key']}` ({item['dataType']}, {required}): {item['name']}{description}")
    lines.append("")


def _roles(lines: list[str], roles: list[dict[str, Any]]) -> None:
    if not roles:
        return
    lines.extend(["## 设备角色", ""])
    for role in roles:
        suffix = f" - {role['description']}" if role["description"] else ""
        lines.append(f"- `{role['key']}`: {role['name']} ({'必填' if role['required'] else '可选'}){suffix}")
    lines.append("")


def _calls(lines, calls, definitions, roles, *, workflow_inputs, step_inputs) -> None:
    if not calls:
        return
    calls_by_id = {item["id"]: item for item in calls}
    lines.extend(["#### 采集信息", ""])
    for call in calls:
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
        call_name = _call_name(call, definition)
        lines.append(f"##### {call_name}")
        lines.append("")
        if call["key"].strip():
            lines.append(f"- 调用 key: `{call['key']}`")
        lines.append(f"- 设备角色: {roles.get(call.get('deviceRoleId'), {}).get('name', '未指定')}")
        lines.append(f"- 样本数量: {call['sampleCount']}")
        if definition:
            lines.append(f"- Collection: {definition['metadata']['name']} (`{definition['key']}`)")
            if definition["spec"]["commandTemplate"]:
                lines.extend(["", "```text", definition["spec"]["commandTemplate"].rstrip(), "```"])
            _bindings(
                lines,
                call["inputBindings"],
                definition["inputs"],
                workflow_inputs=workflow_inputs,
                step_inputs=step_inputs,
                calls=calls_by_id,
                definitions=definitions,
            )
            if definition["outputs"]:
                lines.extend(["", "输出字段:"])
                for item in definition["outputs"]:
                    suffix = f" - {item['description']}" if item["description"] else ""
                    lines.append(f"- `{_call_output_key(call, item)}` ({item['dataType']}): {item['name']}{suffix}")
            samples = [item["name"] for item in definition["spec"]["outputSamples"] if item["name"].strip()]
            if samples:
                lines.extend(["", f"回显示例: {'、'.join(samples)}"])
        lines.append("")


def _bindings(lines, bindings, parameters, *, workflow_inputs, step_inputs, calls, definitions) -> None:
    if not bindings:
        return
    lines.extend(["", "参数绑定:"])
    for parameter in parameters:
        binding = bindings.get(parameter["id"])
        if binding is None:
            continue
        lines.append(
            f"- {parameter['name']} (`{parameter['key']}`): "
            f"{_binding_text(binding, workflow_inputs=workflow_inputs, step_inputs=step_inputs, calls=calls, definitions=definitions)}"
        )


def _binding_text(binding, *, workflow_inputs, step_inputs, calls, definitions) -> str:
    if binding["kind"] == "literal":
        value = json.dumps(binding.get("value"), ensure_ascii=False, sort_keys=True)
        return f"固定值 `{value}`"
    reference = binding["reference"]
    if binding["kind"] == "workflow_input":
        return _named_reference("全局输入", workflow_inputs.get(reference.get("input_id")))
    if binding["kind"] == "step_input":
        return _named_reference("步骤输入", step_inputs.get(reference.get("input_id")))
    if binding["kind"] == "collection_output":
        call = calls.get(reference.get("call_id"))
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"])) if call else None
        output = next((item for item in definition["outputs"] if item["id"] == reference.get("output_id")), None) if definition else None
        if call and output:
            return f"采集“{_call_name(call, definition)}”的输出 `{_call_output_key(call, output)}` ({output['name']})"
    return "无效引用"


def _named_reference(label: str, item: dict[str, Any] | None) -> str:
    if item is None:
        return "无效引用"
    return f"{label} `{item['key']}` ({item['name']})"


def _call_name(call: dict[str, Any], definition: dict[str, Any] | None) -> str:
    return call["name"].strip() or (definition or {}).get("metadata", {}).get("name", "").strip() or "未命名采集"


def _call_output_key(call: dict[str, Any], output: dict[str, Any]) -> str:
    return f"{call['key']}.{output['key']}" if call["key"].strip() else output["key"]


def _transitions(lines, transitions, node_names) -> None:
    if not transitions:
        return
    lines.extend(["#### 跳转到节点", ""])
    for item in transitions:
        condition = item["conditionText"] or "无条件"
        expression = f" (`{item['conditionExpression']}`)" if item["conditionExpression"] else ""
        lines.append(f"- {condition}{expression} -> {node_names.get(item['target']['id'], '未知节点')}")
    lines.append("")


def _paragraph(lines: list[str], value: str) -> None:
    if value.strip():
        lines.extend([value.strip(), ""])
