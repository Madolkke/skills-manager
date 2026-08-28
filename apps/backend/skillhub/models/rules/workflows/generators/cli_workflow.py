from __future__ import annotations

from typing import Any

from .contracts import (
    EMPTY_OPTIONS_SCHEMA,
    WorkflowSkillGeneratorContext,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorResult,
    generated_text_file,
    normalize_empty_options,
)
from .documents import _append_step_summary, _definitions, _finish
from .rendering import (
    append_metadata,
    append_paragraph,
    append_parameters,
    append_schema_children,
    append_script,
    append_transitions,
    binding_field_title,
    binding_text,
    call_name,
    call_output_key,
    frontmatter_lines,
    schema_type,
)


class CliWorkflowSkillGenerator:
    descriptor = WorkflowSkillGeneratorDescriptor(
        id="builtin.cli-workflow",
        version="1.0.0",
        label="CLI 工作流",
        default=False,
        options_schema=EMPTY_OPTIONS_SCHEMA,
    )

    def normalize_options(self, options: object) -> dict[str, Any]:
        return normalize_empty_options(self.descriptor.id, options)

    def generate(self, context: WorkflowSkillGeneratorContext, options: object) -> WorkflowSkillGeneratorResult:
        normalized = self.normalize_options(options)
        files = (
            generated_text_file(
                "SKILL.md",
                render_cli_entry(slug=context.slug, document=context.document),
            ),
            generated_text_file("references/workflow.md", render_cli_workflow_reference(context.document)),
            generated_text_file("references/collections.md", render_cli_collections_reference(context.document)),
        )
        return WorkflowSkillGeneratorResult(descriptor=self.descriptor, options=normalized, files=files)


def render_cli_entry(*, slug: str, document: dict[str, Any]) -> str:
    metadata = document["workflow"]["metadata"]
    lines = [*frontmatter_lines(slug, metadata), "", f"# {metadata['name'] or slug}", ""]
    append_paragraph(lines, metadata["description"])
    lines.extend(
        [
            "## 操作协议",
            "",
            "1. 先读取工作流参考文件，确认全局输入、设备角色、起始步骤和跳转条件。",
            "2. 执行步骤中列出的 CLI 采集命令，按参数绑定填充值，并保留输出字段供后续判断。",
            "3. 按跳转条件推进；条件说明、故障根因和修复建议中的 `{{ expression }}` 保持原文。",
            "4. 脚本步骤仍属于工作流步骤，执行前必须结合目标环境复核脚本草稿。",
            "",
            "## 表达式与模板",
            "",
            "条件说明、故障根因和修复建议支持 `{{ expression }}` 模板。模板只保存原文，不在同步时展开。",
            "可用根包括 `inputs`、`outputs`、`config` 和 `topo`；设备参数通过 `topo.devices.<roleKey>.<property>` 访问。",
            "条件说明可引用所属步骤及传递前序步骤；结论模板可引用能够到达该结论的步骤。未来或无连接步骤不可引用。",
            "",
            "## 参考文件",
            "",
            "- [完整工作流](references/workflow.md)",
            "- [CLI Collection 定义与调用](references/collections.md)",
            "",
        ]
    )
    return _finish(lines)


def render_cli_workflow_reference(document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    metadata = workflow["metadata"]
    node_names = {item["id"]: item["name"] for item in workflow["nodes"]}
    definitions = _cli_definitions(document)
    calls = _cli_call_index(workflow, definitions)
    lines = [f"# {metadata['name']}：完整工作流", ""]
    append_paragraph(lines, metadata["description"])
    append_metadata(lines, metadata)
    append_parameters(lines, "全局输入", workflow["inputs"])
    _append_cli_roles(lines, workflow["deviceRoles"])
    lines.extend(["## 排查步骤", ""])
    for index, step in enumerate((item for item in workflow["nodes"] if "stepType" in item), start=1):
        lines.extend([f"### {index}. {step['name']}", ""])
        _append_step_summary(lines, step)
        _append_step_cli_calls(lines, step, calls)
        append_transitions(lines, step["topology"], node_names)
        append_script(lines, step, include_options=True)
    lines.extend(["## 排查结论", ""])
    for conclusion in (item for item in workflow["nodes"] if item.get("nodeType") == "conclusion"):
        _append_conclusion(lines, conclusion)
    return _finish(lines)


def render_cli_collections_reference(document: dict[str, Any]) -> str:
    workflow = document["workflow"]
    definitions = _cli_definitions(document)
    calls = _cli_call_index(workflow, definitions)
    roles = {item["id"]: item for item in workflow["deviceRoles"]}
    workflow_inputs = {item["id"]: item for item in workflow["inputs"]}
    predecessor_steps = _predecessor_steps(workflow)
    lines = ["# CLI Collection 定义与调用", "", "## Collection 定义", ""]
    if not definitions:
        lines.extend(["当前工作流没有 CLI Collection 定义。", ""])
    for definition in definitions.values():
        _append_cli_definition(lines, definition, level=3)
    lines.extend(["## 工作流中的 CLI 采集调用", ""])
    called = False
    for step in (item for item in workflow["nodes"] if "stepType" in item):
        step_calls = [item for item in step["collectionCalls"] if calls.get(item["id"])]
        if not step_calls:
            continue
        called = True
        lines.extend([f"### {step['name']}", ""])
        for call in step_calls:
            _append_cli_call(
                lines,
                call,
                calls[call["id"]],
                roles,
                workflow_inputs,
                calls,
                predecessor_steps.get(step["id"], set()),
            )
    if not called:
        lines.extend(["当前工作流没有 CLI 采集调用。", ""])
    return _finish(lines)


def _append_cli_roles(lines: list[str], roles: list[dict[str, Any]]) -> None:
    if not roles:
        return
    lines.extend(["## 设备角色", ""])
    for role in roles:
        suffix = f" - {role['description']}" if role["description"] else ""
        lines.append(f"- `{role['key']}`: {role['name']} ({'必填' if role['required'] else '可选'}){suffix}")
        schema = role.get("schema")
        if schema:
            lines.append(f"  - 设备参数: `{schema_type(schema)}`；表达式根: `topo.devices.{role['key']}`")
            _append_role_schema(lines, schema, path=f"topo.devices.{role['key']}", indent="    ")
    lines.append("")


def _append_role_schema(lines: list[str], schema: dict[str, Any], *, path: str, indent: str) -> None:
    if schema.get("type") == "object":
        required = set(schema.get("required", []))
        for key, child in sorted(schema.get("properties", {}).items()):
            necessity = "必填" if key in required else "可选"
            child_path = f"{path}.{key}"
            title = child.get("title") or key
            lines.append(f"{indent}- `{child_path}` ({schema_type(child)}, {necessity}): {title}")
            _append_role_schema(lines, child, path=child_path, indent=f"{indent}  ")
    elif schema.get("type") == "array":
        item_path = f"{path}[0]"
        item_schema = schema.get("items", {})
        lines.append(f"{indent}- `{item_path}` ({schema_type(item_schema)})")
        _append_role_schema(lines, item_schema, path=item_path, indent=f"{indent}  ")


def _append_step_cli_calls(lines: list[str], step: dict[str, Any], calls: dict[str, dict[str, Any]]) -> None:
    visible = [calls[item["id"]] for item in step["collectionCalls"] if item["id"] in calls]
    if not visible:
        return
    lines.extend(["CLI 采集调用:", ""])
    for item in visible:
        call = item["call"]
        definition = item["definition"]
        key = f"，调用 key `{call['key']}`" if call["key"].strip() else ""
        lines.append(f"- {call_name(call, definition)}{key}：Collection `{definition['key']}`")
    lines.append("")


def _append_cli_definition(lines: list[str], definition: dict[str, Any], *, level: int) -> None:
    metadata = definition["metadata"]
    lines.extend([f"{'#' * level} {metadata['name'] or definition['key']}", "", f"- Collection key: `{definition['key']}`"])
    for label, value in (("产业", metadata["industry"]), ("设备", metadata["device"]), ("适用版本", "、".join(metadata["versions"])), ("标签", "、".join(metadata["tags"]))):
        if value:
            lines.append(f"- {label}: {value}")
    lines.append("")
    append_paragraph(lines, metadata["description"])
    command = definition["spec"].get("commandTemplate", "")
    if command:
        lines.extend([f"{'#' * (level + 1)} 采集命令", "", "```text", command.rstrip(), "```", ""])
    append_parameters(lines, "输入参数", definition["inputs"], level=level + 1)
    if definition["outputs"]:
        lines.extend([f"{'#' * (level + 1)} 输出根属性", ""])
        for output in definition["outputs"]:
            schema = output["schema"]
            required = "必填" if output["required"] else "可选"
            title = schema.get("title") or output["key"]
            description = f" - {schema['description']}" if schema.get("description") else ""
            lines.append(f"- `{output['key']}` ({schema_type(schema)}, {required}): {title}{description}")
            append_schema_children(lines, schema, indent="  ")
        lines.append("")


def _append_cli_call(lines: list[str], call: dict[str, Any], item: dict[str, Any], roles, workflow_inputs, calls, predecessor_ids: set[str]) -> None:
    definition = item["definition"]
    role = roles.get(call.get("deviceRoleId")) if isinstance(call.get("deviceRoleId"), str) else None
    lines.extend([f"#### {call_name(call, definition)}", ""])
    if call["key"].strip():
        lines.append(f"- 调用 key: `{call['key']}`")
    lines.append(f"- 设备角色: {(role or {}).get('name', '单设备')}")
    lines.append(f"- 采集次数: {call['sampleCount']}")
    lines.append(f"- Collection: `{definition['key']}`")
    command = definition["spec"].get("commandTemplate", "")
    if command:
        lines.extend(["", "```text", command.rstrip(), "```"])
    _append_cli_bindings(lines, call, item, definition["inputs"], workflow_inputs, calls, predecessor_ids, roles)
    if definition["outputs"]:
        lines.extend(["", "输出字段:"])
        for output in definition["outputs"]:
            schema = output["schema"]
            lines.append(f"- `{call_output_key(call, output)}` ({schema_type(schema)})")
            append_schema_children(lines, schema, indent="  ")
    lines.append("")


def _append_cli_bindings(lines, call, item, parameters, workflow_inputs, calls, predecessor_ids: set[str], roles) -> None:
    entries = []
    for parameter in parameters:
        binding = call["inputBindings"].get(parameter["id"])
        if binding is None:
            continue
        if binding["kind"] == "collection_output":
            source = calls.get(binding.get("reference", {}).get("call_id"))
            if source is None:
                continue
            if source["step"]["id"] == item["step"]["id"] and source["index"] >= item["index"]:
                continue
            if source["step"]["id"] != item["step"]["id"] and source["step"]["id"] not in predecessor_ids:
                continue
            text = _cli_binding_text(binding, source)
            if not text:
                continue
        else:
            text = binding_text(binding, workflow_inputs=workflow_inputs, calls={}, definitions={}, roles=roles)
        entries.append(f"- {binding_field_title(parameter)} (`{parameter['key']}`): {text}")
    if entries:
        lines.extend(["", "参数绑定:", *entries])


def _cli_binding_text(binding, source) -> str:
    source_call = source["call"]
    output = next((item for item in source["definition"]["outputs"] if item["id"] == binding.get("reference", {}).get("output_id")), None)
    if output is None:
        return ""
    return f"采集“{call_name(source_call, source['definition'])}”的输出 `{call_output_key(source_call, output, indexed=False)}`"


def _cli_call_index(workflow: dict[str, Any], definitions: dict[tuple[str, int], dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for step in (item for item in workflow["nodes"] if "stepType" in item):
        for index, call in enumerate(step["collectionCalls"]):
            definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
            if definition is not None:
                result[call["id"]] = {"call": call, "definition": definition, "step": step, "index": index}
    return result


def _cli_definitions(document: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    return {key: value for key, value in _definitions(document).items() if value["spec"]["collectionType"] == "cli"}


def _predecessor_steps(workflow: dict[str, Any]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for node in workflow["nodes"]:
        for transition in node.get("topology", []):
            reverse.setdefault(transition["target"]["id"], set()).add(node["id"])
    result: dict[str, set[str]] = {}
    for node in workflow["nodes"]:
        visible: set[str] = set()
        pending = list(reverse.get(node["id"], set()))
        while pending:
            source = pending.pop()
            if source in visible:
                continue
            visible.add(source)
            pending.extend(reverse.get(source, set()))
        result[node["id"]] = visible
    return result


def _append_conclusion(lines: list[str], conclusion: dict[str, Any]) -> None:
    labels = {"info": "信息", "warning": "警告", "error": "错误", "critical": "严重"}
    lines.extend([f"### {conclusion['name']}", "", f"- 严重等级: {labels.get(conclusion.get('severity', 'info'), conclusion.get('severity', 'info'))}", f"- 故障根因: {conclusion['rootCause'] or '未填写'}", f"- 修复建议: {conclusion['repairRecommendation'] or '未填写'}", ""])
