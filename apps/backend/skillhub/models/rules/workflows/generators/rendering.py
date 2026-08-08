from __future__ import annotations

import json
from typing import Any, Callable

import yaml


def frontmatter_lines(slug: str, metadata: dict[str, Any]) -> list[str]:
    frontmatter = yaml.safe_dump(
        {"name": slug, "description": metadata["description"]},
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).strip()
    return ["---", frontmatter, "---"]


def append_metadata(lines: list[str], metadata: dict[str, Any]) -> None:
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


def append_parameters(lines: list[str], heading: str, parameters: list[dict[str, Any]], *, level: int | None = None) -> None:
    if not parameters:
        return
    prefix = "#" * (level if level is not None else (2 if heading == "全局输入" else 4))
    lines.extend([f"{prefix} {heading}", ""])
    for item in parameters:
        required = "必填" if item["required"] else "可选"
        schema = item["schema"]
        description = f" - {schema['description']}" if schema.get("description") else ""
        title = schema.get("title") or item["key"]
        lines.append(f"- `{item['key']}` ({schema_type(schema)}, {required}): {title}{description}")
        append_schema_children(lines, schema, indent="  ")
    lines.append("")


def append_roles(lines: list[str], roles: list[dict[str, Any]]) -> None:
    if not roles:
        return
    lines.extend(["## 设备角色", ""])
    for role in roles:
        suffix = f" - {role['description']}" if role["description"] else ""
        lines.append(f"- `{role['key']}`: {role['name']} ({'必填' if role['required'] else '可选'}){suffix}")
    lines.append("")


def append_calls(
    lines: list[str],
    calls: list[dict[str, Any]],
    definitions: dict[tuple[str, int], dict[str, Any]],
    roles: dict[str, dict[str, Any]],
    *,
    workflow_inputs: dict[str, dict[str, Any]],
    level: int = 4,
    collection_link: Callable[[dict[str, Any]], str] | None = None,
) -> None:
    if not calls:
        return
    calls_by_id = {item["id"]: item for item in calls}
    lines.extend([f"{'#' * level} 采集信息", ""])
    for call in calls:
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
        role_id = call.get("deviceRoleId")
        role = roles.get(role_id) if isinstance(role_id, str) else None
        lines.extend([f"{'#' * (level + 1)} {call_name(call, definition)}", ""])
        if call["key"].strip():
            lines.append(f"- 调用 key: `{call['key']}`")
        collection_type = definition["spec"]["collectionType"] if definition else None
        is_log = collection_type == "log"
        is_config = collection_type == "config"
        if is_log:
            lines.append("- 采集类型: 全局日志")
        elif is_config:
            lines.append("- 采集类型: 配置匹配")
        else:
            lines.append(f"- 设备角色: {(role or {}).get('name', '单设备')}")
            lines.append(f"- 采集次数: {call['sampleCount']}")
        if definition:
            lines.append(f"- Collection: {definition['metadata']['name']} (`{definition['key']}`)")
            if collection_link:
                lines.append(f"- Collection 文件: [{definition['metadata']['name']}]({collection_link(definition)})")
            spec = definition["spec"]
            if spec["collectionType"] == "cli" and spec["commandTemplate"]:
                lines.extend(["", "```text", spec["commandTemplate"].rstrip(), "```"])
            elif spec["collectionType"] == "log":
                append_log_queries(lines, spec["queries"], definition["outputs"])
            elif spec["collectionType"] == "config":
                append_config_commands(lines, spec.get("config", {}).get("commands", []), level=5)
            append_bindings(
                lines,
                call["inputBindings"],
                definition["inputs"],
                workflow_inputs=workflow_inputs,
                calls=calls_by_id,
                definitions=definitions,
            )
            if definition["outputs"]:
                lines.extend(["", "输出字段:"])
                for item in definition["outputs"]:
                    schema = item["schema"]
                    required = "必填" if item["required"] else "可选"
                    description = f" - {schema['description']}" if schema.get("description") else ""
                    title = schema.get("title") or item["key"]
                    lines.append(f"- `{call_output_key(call, item)}` ({schema_type(schema)}, {required}): {title}{description}")
                    append_schema_children(lines, schema, indent="  ")
            samples = [item["name"] for item in spec.get("outputSamples", []) if item["name"].strip()]
            if samples:
                heading = "回显示例" if spec["collectionType"] == "cli" else "日志输出示例"
                lines.extend(["", f"{heading}: {'、'.join(samples)}"])
        lines.append("")


def append_bindings(lines, bindings, parameters, *, workflow_inputs, calls, definitions) -> None:
    if not bindings:
        return
    lines.extend(["", "参数绑定:"])
    for parameter in parameters:
        binding = bindings.get(parameter["id"])
        if binding is None:
            continue
        title = binding_field_title(parameter)
        lines.append(f"- {title} (`{parameter['key']}`): {binding_text(binding, workflow_inputs=workflow_inputs, calls=calls, definitions=definitions)}")


def binding_text(binding, *, workflow_inputs, calls, definitions) -> str:
    if binding["kind"] == "literal":
        value = json.dumps(binding.get("value"), ensure_ascii=False, sort_keys=True)
        return f"固定值 `{value}`"
    reference = binding["reference"]
    if binding["kind"] == "workflow_input":
        return named_reference("全局输入", workflow_inputs.get(reference.get("input_id")))
    if binding["kind"] == "collection_output":
        call = calls.get(reference.get("call_id"))
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"])) if call else None
        output = next((item for item in definition["outputs"] if item["id"] == reference.get("output_id")), None) if definition else None
        if call and output:
            return f"采集“{call_name(call, definition)}”的输出 `{call_output_key(call, output, indexed=False)}`"
    return "无效引用"


def append_log_queries(
    lines: list[str],
    queries: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> None:
    if not queries:
        return
    output_keys = {item["id"]: item["key"] for item in outputs}
    lines.extend(["", "日志聚合 SQL:"])
    for query in queries:
        title = query["name"].strip() or query["id"]
        mapped = [output_keys.get(item, item) for item in query["outputIds"]]
        lines.extend([f"- 查询 `{title}` (输出: {', '.join(f'`{item}`' for item in mapped) or '无'})", "", "```sql", query["sql"].rstrip(), "```"])


def append_config_commands(lines: list[str], commands: list[dict[str, Any]], *, level: int) -> None:
    if not commands:
        return
    lines.extend(["", "配置命令树:"])
    for command in commands:
        append_config_command(lines, command, level=level)


def append_config_command(lines: list[str], command: dict[str, Any], *, level: int) -> None:
    suffix = "非唯一" if command.get("unique") is False else "唯一"
    lines.extend([f"{'#' * level} {command['name']}（{suffix}）", f"- 模式: `{command['pattern']}`"])
    for name, schema in command.get("captures", {}).items():
        lines.append(f"- 捕获 `{name}` ({schema_type(schema)}): {schema.get('title') or name}")
    lines.append("")
    for child in command.get("children", []):
        append_config_command(lines, child, level=level + 1)


def named_reference(label: str, item: dict[str, Any] | None) -> str:
    if item is None:
        return "无效引用"
    return f"{label} `{item['key']}` ({binding_field_title(item)})"


def binding_field_title(field: dict[str, Any]) -> str:
    return str(field.get("schema", {}).get("title") or field.get("key") or "未命名字段")


def schema_type(schema: dict[str, Any]) -> str:
    return str(schema.get("type") or "any")


def append_schema_children(lines: list[str], schema: dict[str, Any], *, indent: str) -> None:
    schema_kind = schema.get("type")
    if schema_kind == "object":
        required = set(schema.get("required", []))
        for key, child in sorted(schema.get("properties", {}).items()):
            necessity = "必填" if key in required else "可选"
            title = child.get("title") or key
            description = f" - {child['description']}" if child.get("description") else ""
            lines.append(f"{indent}- `{key}` ({schema_type(child)}, {necessity}): {title}{description}")
            append_schema_children(lines, child, indent=f"{indent}  ")
        return
    if schema_kind == "array":
        item_schema = schema.get("items", {})
        title = item_schema.get("title")
        description = f" - {item_schema['description']}" if item_schema.get("description") else ""
        detail = f": {title}{description}" if title else description
        lines.append(f"{indent}- 数组元素 ({schema_type(item_schema)}){detail}")
        append_schema_children(lines, item_schema, indent=f"{indent}  ")


def call_name(call: dict[str, Any], definition: dict[str, Any] | None) -> str:
    return call["name"].strip() or (definition or {}).get("metadata", {}).get("name", "").strip() or "未命名采集"


def call_output_key(call: dict[str, Any], output: dict[str, Any], *, indexed: bool = True) -> str:
    call_key = call["key"].strip()
    if not call_key:
        return output["key"]
    path = f"outputs.{call_key}"
    if indexed and int(call.get("sampleCount", 1)) > 1:
        path += "[i]"
    return f"{path}.{output['key']}"


def append_transitions(lines: list[str], transitions, node_names, *, level: int = 4) -> None:
    if not transitions:
        return
    lines.extend([f"{'#' * level} 跳转到节点", ""])
    for item in transitions:
        condition = item["conditionText"] or "无条件"
        expression = f" (`{item['conditionExpression']}`)" if item["conditionExpression"] else ""
        lines.append(f"- {condition}{expression} -> {node_names.get(item['target']['id'], '未知节点')}")
    lines.append("")


def append_script(lines: list[str], step: dict[str, Any], *, level: int = 4, include_options: bool = False) -> None:
    if step["stepType"] != "script" or not step.get("script", {}).get("source", "").strip():
        return
    script = step["script"]
    lines.extend([f"{'#' * level} 脚本草稿", "", f"```{script.get('language') or 'text'}", script["source"].rstrip(), "```", ""])
    if include_options and script.get("options"):
        options = json.dumps(script["options"], ensure_ascii=False, sort_keys=True, indent=2)
        lines.extend([f"{'#' * level} 脚本选项", "", "```json", options, "```", ""])


def append_paragraph(lines: list[str], value: str) -> None:
    if value.strip():
        lines.extend([value.strip(), ""])
