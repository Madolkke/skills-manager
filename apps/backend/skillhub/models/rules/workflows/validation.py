from __future__ import annotations

from collections import Counter, deque
from typing import Any
from urllib.parse import quote

from .collection_validation import validate_collection_identity
from .config_validation import config_root_names
from .expression import validate_expression
from .expression.checker import SAMPLE_INDEX_DIAGNOSTIC_CODES
from .expression.environment import (
    binding_scope_calls,
    conclusion_scope_steps,
    expression_scope_steps,
    is_expression_identifier,
    project_workflow_expression_environment,
)
from .json_schema import schema_title, schemas_assignable, value_matches_schema
from .templates import validate_template
from .validation_helpers import append_duplicates, append_legacy_schema_warnings, append_missing_titles, append_optional_duplicates, issue


def _is_device_identifier(value: str) -> bool:
    return is_expression_identifier(value) and not value.startswith("_")


def _append_device_role_schema_issues(roles, issues) -> None:
    for role in roles:
        selection = {"type": "roles", "itemId": role.get("id", "")}
        key = str(role.get("key", "")).strip()
        if not _is_device_identifier(key):
            issues.append(issue("INVALID_ROLE_KEY", "error", f"设备角色 key“{key}”必须是合法的 Python 标识符且不能以下划线开头。", {**selection, "field": "key"}))
        schema = role.get("schema")
        if schema is None:
            continue
        if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict) or not isinstance(schema.get("required"), list) or schema.get("additionalProperties") is not False:
            issues.append(issue("DEVICE_ROLE_SCHEMA_OBJECT_REQUIRED", "error", "设备角色参数 Schema 根节点必须是 object，并包含 properties、required 和 additionalProperties=false。", {**selection, "field": "schema"}))
            continue
        _append_device_schema_node_issues(schema, selection, issues, "schema")


def _append_device_schema_node_issues(schema, selection, issues, path: str) -> None:
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if len(required) != len(set(required)) or not set(required).issubset(properties):
            issues.append(issue("DEVICE_ROLE_SCHEMA_REQUIRED_INVALID", "error", "设备角色 Schema 的 required 必须唯一且只能引用已有属性。", {**selection, "field": path}))
        for key, child in properties.items():
            if not _is_device_identifier(str(key)):
                issues.append(issue("INVALID_DEVICE_ROLE_PROPERTY_KEY", "error", f"设备属性 key“{key}”必须是合法的 Python 标识符且不能以下划线开头。", {**selection, "field": f"{path}.properties.{key}"}))
            _append_device_schema_node_issues(child, selection, issues, f"{path}.properties.{key}")
    elif schema.get("type") == "array":
        _append_device_schema_node_issues(schema.get("items", {}), selection, issues, f"{path}.items")


def validate_workflow_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    workflow = document["workflow"]
    snapshots = document.get("collectionSnapshots", [])
    definitions = {(item["id"], item["revision"]): item for item in snapshots}
    steps = [item for item in workflow["nodes"] if "stepType" in item]
    conclusions = [item for item in workflow["nodes"] if item.get("nodeType") == "conclusion"]
    issues: list[dict[str, Any]] = []

    if not workflow["metadata"]["name"].strip():
        issues.append(issue("MISSING_WORKFLOW_NAME", "error", "工作流名称不能为空。", {"type": "metadata", "field": "name"}))
    if not workflow["metadata"]["description"].strip():
        issues.append(issue("MISSING_WORKFLOW_DESCRIPTION", "error", "工作流说明不能为空。", {"type": "metadata", "field": "description"}))

    _duplicate_issues(workflow, steps, issues)
    _append_device_role_schema_issues(workflow["deviceRoles"], issues)
    validate_collection_identity(snapshots, issues)
    _validate_config_root_conflicts(steps, definitions, issues)
    if not any(step["isStart"] for step in steps):
        issues.append(issue("NO_START_STEP", "error", "工作流至少需要一个起始步骤。", {"type": "metadata"}))

    node_by_id = {node["id"]: node for node in workflow["nodes"]}
    role_ids = {role["id"] for role in workflow["deviceRoles"]}
    workflow_inputs = {item["id"]: item for item in workflow["inputs"]}
    workflow_input_keys = {item["key"].strip() for item in workflow["inputs"] if item["key"].strip()}
    reported_unscoped_conflicts: set[tuple[str, str, str]] = set()
    for step in steps:
        _validate_step(
            step,
            steps,
            definitions,
            node_by_id,
            role_ids,
            workflow_inputs,
            workflow["deviceRoles"],
            workflow_input_keys,
            issues,
            reported_unscoped_conflicts,
        )

    for conclusion in conclusions:
        environment = project_workflow_expression_environment(
            conclusion_scope_steps(workflow["nodes"], conclusion["id"]),
            definitions,
            {item["key"].strip(): item["schema"] for item in workflow["inputs"] if item["key"].strip()},
            workflow["deviceRoles"],
        )
        for field in ("rootCause", "repairRecommendation"):
            for diagnostic in validate_template(conclusion.get(field, ""), environment):
                issues.append(
                    issue(
                        diagnostic["code"],
                        "error" if diagnostic["severity"] == "error" else "warning",
                        diagnostic["message"],
                        {"type": "conclusion", "id": conclusion["id"], "field": field},
                    )
                )

    reachable = _reachable_nodes(steps)
    for node in [*steps, *conclusions]:
        if not node.get("isStart") and node["id"] not in reachable:
            issues.append(
                issue("UNREACHABLE_NODE", "warning", f"节点“{node['name']}”无法从任何起始步骤到达。", _selection(node))
            )
    cycle = _cycle_members(steps)
    if cycle:
        names = [node_by_id[item]["name"] for item in cycle if item in node_by_id]
        issues.append(issue("POTENTIAL_CYCLE", "warning", f"检测到可能的循环路径：{' -> '.join(names)}。", {"type": "step", "id": cycle[0]}))
    return _assign_issue_ids(issues)


def _duplicate_issues(workflow, steps, issues) -> None:
    append_duplicates(workflow["nodes"], "id", "MISSING_NODE_ID", "DUPLICATE_NODE_ID", "节点 ID", issues, {"type": "metadata"})
    append_duplicates(workflow["inputs"], "id", "MISSING_INPUT_ID", "DUPLICATE_INPUT_ID", "全局输入 ID", issues, {"type": "inputs"})
    append_duplicates(workflow["inputs"], "key", "MISSING_INPUT_KEY", "DUPLICATE_INPUT_KEY", "全局输入 key", issues, {"type": "inputs"})
    append_missing_titles(workflow["inputs"], "全局输入名称", issues, {"type": "inputs"})
    append_legacy_schema_warnings(workflow["inputs"], issues, {"type": "inputs"})
    append_duplicates(workflow["deviceRoles"], "id", "MISSING_ROLE_ID", "DUPLICATE_ROLE_ID", "设备角色 ID", issues, {"type": "roles"})
    append_duplicates(workflow["deviceRoles"], "key", "MISSING_ROLE_KEY", "DUPLICATE_ROLE_KEY", "设备角色 key", issues, {"type": "roles"})
    for step in steps:
        selection = {"type": "step", "id": step["id"]}
        append_duplicates(step["collectionCalls"], "id", "MISSING_CALL_ID", "DUPLICATE_CALL_ID", "采集调用 ID", issues, {**selection, "section": "collections"})
        append_optional_duplicates(step["collectionCalls"], "key", "DUPLICATE_CALL_KEY", "采集调用 key", issues, {**selection, "section": "collections"})
        append_duplicates(step["topology"], "id", "MISSING_TRANSITION_ID", "DUPLICATE_TRANSITION_ID", "跳转 ID", issues, {**selection, "section": "paths"})


def _validate_config_root_conflicts(steps, definitions, issues) -> None:
    contexts: dict[str, dict[str, str]] = {}
    for step in steps:
        for call in step["collectionCalls"]:
            definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
            if not definition or definition["spec"]["collectionType"] != "config":
                continue
            context = call.get("deviceRoleId") or "__default__"
            names = contexts.setdefault(context, {})
            selection = {"type": "step", "id": step["id"], "section": "collections", "itemId": call["id"]}
            for name in config_root_names(definition["spec"]):
                if name in names:
                    issues.append(
                        issue(
                            "CONFIG_ROOT_COMMAND_CONFLICT",
                            "error",
                            f"同一设备上下文中的配置根命令“{name}”重复。",
                            {**selection, "field": "definition.spec.config.commands"},
                        )
                    )
                else:
                    names[name] = call["id"]


def _validate_step(
    step,
    all_steps,
    definitions,
    node_by_id,
    role_ids,
    workflow_inputs,
    workflow_roles,
    workflow_input_keys,
    issues,
    reported_unscoped_conflicts,
) -> None:
    selection = {"type": "step", "id": step["id"]}
    _append_visible_unscoped_conflicts(
        step=step,
        all_steps=all_steps,
        definitions=definitions,
        workflow_input_keys=workflow_input_keys,
        issues=issues,
        reported=reported_unscoped_conflicts,
    )
    for call in step["collectionCalls"]:
        call_selection = {**selection, "section": "collections", "itemId": call["id"]}
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
        call_label = _call_label(call, definition) if definition else call["name"] or "未命名采集"
        if definition is None:
            if call["sampleCount"] < 1:
                issues.append(issue("INVALID_SAMPLE_COUNT", "error", f"采集“{call_label}”的采集次数必须大于零。", {**call_selection, "field": "sampleCount"}))
            issues.append(issue("BROKEN_REFERENCE", "error", f"采集“{call_label}”引用的定义版本不存在。", call_selection))
            continue
        if definition["spec"]["collectionType"] == "log":
            if call.get("deviceRoleId"):
                issues.append(issue("LOG_CALL_DEVICE_ROLE_UNSUPPORTED", "error", f"日志采集“{call_label}”不能绑定设备角色。", {**call_selection, "field": "deviceRoleId"}))
            if call["sampleCount"] != 1:
                issues.append(issue("LOG_CALL_SAMPLE_COUNT_UNSUPPORTED", "error", f"日志采集“{call_label}”的采集次数必须为 1。", {**call_selection, "field": "sampleCount"}))
        elif definition["spec"]["collectionType"] == "config":
            if call["sampleCount"] != 1:
                issues.append(issue("CONFIG_CALL_SAMPLE_COUNT_UNSUPPORTED", "error", f"配置采集“{call_label}”的采集次数必须为 1。", {**call_selection, "field": "sampleCount"}))
            if call.get("deviceRoleId") and call["deviceRoleId"] not in role_ids:
                issues.append(issue("BROKEN_REFERENCE", "error", f"采集“{call['name']}”引用的设备角色不存在。", {**call_selection, "field": "deviceRoleId"}))
        else:
            if call["sampleCount"] < 1:
                issues.append(issue("INVALID_SAMPLE_COUNT", "error", f"采集“{call_label}”的采集次数必须大于零。", {**call_selection, "field": "sampleCount"}))
            elif call["sampleCount"] > 1:
                key = call["key"].strip()
                if not key:
                    issues.append(issue("MULTI_SAMPLE_CALL_KEY_REQUIRED", "error", f"多次采集“{call_label}”必须填写调用 key。", {**call_selection, "field": "key"}))
                elif not is_expression_identifier(key):
                    issues.append(issue("INVALID_MULTI_SAMPLE_CALL_KEY", "error", f"多次采集“{call_label}”的调用 key 必须是合法的 Python 标识符。", {**call_selection, "field": "key"}))
            if call.get("deviceRoleId") and call["deviceRoleId"] not in role_ids:
                issues.append(issue("BROKEN_REFERENCE", "error", f"采集“{call['name']}”引用的设备角色不存在。", {**call_selection, "field": "deviceRoleId"}))
        visible_calls, all_calls = binding_scope_calls(all_steps, step["id"], call["id"])
        for parameter in definition["inputs"]:
            binding = call["inputBindings"].get(parameter["id"])
            binding_selection = {**call_selection, "field": f"binding.{parameter['id']}"}
            if parameter["required"] and not _binding_has_value(binding):
                issues.append(issue("MISSING_REQUIRED_BINDING", "error", f"采集“{call_label}”尚未绑定必填参数“{schema_title(parameter)}”。", binding_selection))
            if binding:
                _validate_binding(binding, parameter, workflow_inputs, visible_calls, all_calls, definitions, issues, binding_selection, step["id"])
    for transition in step["topology"]:
        target = node_by_id.get(transition["target"]["id"])
        if target is None:
            issues.append(issue("BROKEN_REFERENCE", "error", f"步骤“{step['name']}”存在无效跳转目标。", selection))
        expression_result = validate_expression(
            transition.get("conditionExpression", ""),
            _step_expression_environment(step, definitions, workflow_inputs, workflow_roles=workflow_roles, all_steps=all_steps),
        )
        for diagnostic in expression_result["diagnostics"]:
            severity = _expression_diagnostic_severity(diagnostic["code"])
            if severity is None:
                continue
            issues.append(
                issue(
                    diagnostic["code"],
                    severity,
                    diagnostic["message"],
                    {**selection, "section": "paths", "itemId": transition["id"], "field": "conditionExpression"},
                )
            )


def _step_expression_environment(
    step,
    definitions,
    workflow_inputs,
    *,
    workflow_roles=None,
    all_steps=None,
) -> dict[str, Any]:
    """Build the condition environment for a step and its graph predecessors."""
    if all_steps is None:
        # Keep the helper usable by legacy rule tests that pass a minimal step
        # mapping without the normalized ``stepType`` discriminator.
        scoped_steps = [step]
    else:
        scoped_steps = expression_scope_steps(all_steps, step.get("id"))
    inputs = {
        item["key"].strip(): item["schema"]
        for item in workflow_inputs.values()
        if item["key"].strip()
    }
    return project_workflow_expression_environment(scoped_steps, definitions, inputs, workflow_roles or [])


def _expression_diagnostic_severity(code: str) -> str | None:
    if code in {"CONFIG_STRING_SUBSCRIPT_FORBIDDEN", "CONFIG_ARRAY_INDEX_INVALID"}:
        return "error"
    if code in SAMPLE_INDEX_DIAGNOSTIC_CODES:
        return "warning"
    return None


def _append_visible_unscoped_conflicts(
    *,
    step,
    all_steps,
    definitions,
    workflow_input_keys,
    issues,
    reported,
) -> None:
    """Report direct-output conflicts in the environment visible at ``step``."""
    visible_steps = expression_scope_steps(all_steps, step.get("id"))
    candidates: dict[str, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = {}
    for visible_step in visible_steps:
        for call in visible_step.get("collectionCalls", []):
            if str(call.get("key", "")).strip():
                continue
            if max(int(call.get("sampleCount", 1)), 1) > 1:
                continue
            reference = call.get("definition", {})
            definition = definitions.get((reference.get("id"), reference.get("revision")))
            if definition is None:
                continue
            for output in definition.get("outputs", []):
                key = str(output.get("key", "")).strip()
                if not is_expression_identifier(key):
                    continue
                candidates.setdefault(key, []).append((visible_step, call, definition))
    for key, entries in candidates.items():
        if key not in workflow_input_keys and len(entries) < 2:
            continue
        for owner_step, call, definition in entries:
            conflict_id = (
                str(owner_step.get("id", "")),
                str(call.get("id", "")),
                key,
            )
            if conflict_id in reported:
                continue
            reported.add(conflict_id)
            selection = {
                "type": "step",
                "id": owner_step["id"],
                "section": "collections",
                "itemId": call["id"],
            }
            issues.append(
                issue(
                    "UNSCOPED_OUTPUT_CONFLICT",
                    "error",
                    f"采集“{_call_label(call, definition)}”直接暴露的输出字段“{key}”与 Workflow 全局输入或其他直接输出重名，请填写调用 key 作为命名空间。",
                    selection,
                )
            )


def _call_label(call, definition) -> str:
    return call["name"].strip() or definition["metadata"]["name"].strip() or definition["key"]


def _validate_binding(binding, parameter, workflow_inputs, calls, all_calls, definitions, issues, selection, current_step_id) -> None:
    kind = binding["kind"]
    ref = binding["reference"]
    valid = kind == "literal"
    if kind == "workflow_input":
        valid = ref.get("input_id") in workflow_inputs
    elif kind == "collection_output":
        entry = calls.get(ref.get("call_id"))
        call = entry["call"] if entry else None
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"])) if call else None
        valid = bool(definition and any(item["id"] == ref.get("output_id") for item in definition["outputs"]))
    if not valid:
        entry = all_calls.get(ref.get("call_id")) if kind == "collection_output" else None
        if kind == "collection_output" and entry and entry["stepId"] == current_step_id:
            issues.append(issue("FORWARD_OUTPUT_BINDING", "error", "采集输出只能引用当前调用之前或传递前序步骤中的采集。", selection))
            return
        issues.append(issue("BROKEN_REFERENCE", "error", f"参数绑定类型“{kind}”的引用无效。", selection))
        return
    if kind == "literal" and not value_matches_schema(binding.get("value"), parameter["schema"]):
        issues.append(issue("LITERAL_SCHEMA_MISMATCH", "warning", f"字段“{schema_title(parameter)}”的固定值与 Schema 不匹配。", selection))
    source = workflow_inputs.get(ref.get("input_id")) if kind == "workflow_input" else None
    if kind == "collection_output":
        call = calls[ref["call_id"]]["call"]
        definition = definitions[(call["definition"]["id"], call["definition"]["revision"])]
        source = next(item for item in definition["outputs"] if item["id"] == ref["output_id"])
    if source and not schemas_assignable(source["schema"], parameter["schema"]):
        issues.append(issue("INCOMPATIBLE_BINDING_SCHEMA", "error", f"来源字段“{schema_title(source)}”与输入“{schema_title(parameter)}”的 Schema 不兼容。", selection))


def _binding_has_value(binding) -> bool:
    if not binding:
        return False
    return binding["kind"] != "literal" or binding.get("value") not in (None, "")


def _reachable_nodes(steps) -> set[str]:
    step_by_id = {item["id"]: item for item in steps}
    queue = deque(item["id"] for item in steps if item["isStart"])
    reached: set[str] = set()
    while queue:
        node_id = queue.popleft()
        if node_id in reached:
            continue
        reached.add(node_id)
        for transition in step_by_id.get(node_id, {}).get("topology", []):
            queue.append(transition["target"]["id"])
    return reached


def _cycle_members(steps) -> list[str]:
    step_ids = {item["id"] for item in steps}
    adjacency = {item["id"]: [edge["target"]["id"] for edge in item["topology"] if edge["target"]["id"] in step_ids] for item in steps}
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node_id: str) -> list[str]:
        if node_id in visiting:
            return visiting[visiting.index(node_id) :]
        if node_id in visited:
            return []
        visiting.append(node_id)
        for target in adjacency.get(node_id, []):
            cycle = visit(target)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(node_id)
        return []

    for step in steps:
        cycle = visit(step["id"])
        if cycle:
            return cycle
    return []


def _selection(node) -> dict[str, str]:
    return {"type": "step" if "stepType" in node else "conclusion", "id": node["id"]}


def _assign_issue_ids(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("type", "id", "revision", "section", "itemId", "field")
    occurrences: Counter[str] = Counter()
    for validation_issue in issues:
        parts = [validation_issue["code"].lower(), *(str(validation_issue["selection"].get(field, "")) for field in fields)]
        base = "/".join(["workflow-issue", *(quote(part, safe="-._~") for part in parts)])
        occurrence = occurrences[base]
        occurrences[base] += 1
        validation_issue["id"] = f"{base}/{occurrence}"
    return issues
