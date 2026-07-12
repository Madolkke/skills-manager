from __future__ import annotations

from collections import Counter, deque
from typing import Any


def validate_workflow_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    workflow = document["workflow"]
    snapshots = document.get("collectionSnapshots", [])
    definitions = {(item["id"], item["revision"]): item for item in snapshots}
    steps = [item for item in workflow["nodes"] if "stepType" in item]
    conclusions = [item for item in workflow["nodes"] if item.get("nodeType") == "conclusion"]
    issues: list[dict[str, Any]] = []

    if not workflow["metadata"]["name"].strip():
        issues.append(_issue("MISSING_WORKFLOW_NAME", "error", "工作流名称不能为空。", {"type": "metadata"}))
    if not workflow["metadata"]["description"].strip():
        issues.append(_issue("MISSING_WORKFLOW_DESCRIPTION", "error", "工作流说明不能为空。", {"type": "metadata"}))

    _duplicate_issues(workflow, steps, issues)
    _collection_identity_issues(snapshots, issues)
    if not any(step["isStart"] for step in steps):
        issues.append(_issue("NO_START_STEP", "error", "工作流至少需要一个起始步骤。", {"type": "metadata"}))

    node_by_id = {node["id"]: node for node in workflow["nodes"]}
    role_ids = {role["id"] for role in workflow["deviceRoles"]}
    workflow_input_ids = {item["id"] for item in workflow["inputs"]}
    workflow_input_keys = {item["key"].strip() for item in workflow["inputs"] if item["key"].strip()}
    for step in steps:
        _validate_step(step, definitions, node_by_id, role_ids, workflow_input_ids, workflow_input_keys, issues)

    reachable = _reachable_nodes(steps)
    for node in [*steps, *conclusions]:
        if not node.get("isStart") and node["id"] not in reachable:
            issues.append(
                _issue("UNREACHABLE_NODE", "warning", f"节点“{node['name']}”无法从任何起始步骤到达。", _selection(node))
            )
    cycle = _cycle_members(steps)
    if cycle:
        names = [node_by_id[item]["name"] for item in cycle if item in node_by_id]
        issues.append(_issue("POTENTIAL_CYCLE", "warning", f"检测到可能的循环路径：{' -> '.join(names)}。", {"type": "step", "id": cycle[0]}))
    return issues


def _duplicate_issues(workflow, steps, issues) -> None:
    _append_duplicates(workflow["nodes"], "id", "DUPLICATE_NODE_ID", "节点 ID", issues, {"type": "metadata"})
    _append_duplicates(workflow["inputs"], "id", "DUPLICATE_INPUT_ID", "全局输入 ID", issues, {"type": "inputs"})
    _append_duplicates(workflow["inputs"], "key", "DUPLICATE_INPUT_KEY", "全局输入 key", issues, {"type": "inputs"})
    _append_missing_names(workflow["inputs"], "全局输入名称", issues, {"type": "inputs"})
    _append_duplicates(workflow["deviceRoles"], "id", "DUPLICATE_ROLE_ID", "设备角色 ID", issues, {"type": "roles"})
    _append_duplicates(workflow["deviceRoles"], "key", "DUPLICATE_ROLE_KEY", "设备角色 key", issues, {"type": "roles"})
    for step in steps:
        selection = {"type": "step", "id": step["id"]}
        parameters = [item["parameter"] for item in step["inputs"]]
        _append_duplicates(parameters, "id", "DUPLICATE_STEP_INPUT_ID", "步骤输入 ID", issues, selection)
        _append_duplicates(parameters, "key", "DUPLICATE_STEP_INPUT_KEY", "步骤输入 key", issues, selection)
        _append_missing_names(parameters, "步骤输入名称", issues, selection)
        _append_duplicates(step["collectionCalls"], "id", "DUPLICATE_CALL_ID", "采集调用 ID", issues, selection)
        _append_optional_duplicates(step["collectionCalls"], "key", "DUPLICATE_CALL_KEY", "采集调用 key", issues, selection)
        _append_duplicates(step["topology"], "id", "DUPLICATE_TRANSITION_ID", "跳转 ID", issues, selection)


def _collection_identity_issues(definitions, issues) -> None:
    references = [{"reference": f"{item['id']}@{item['revision']}"} for item in definitions]
    _append_duplicates(references, "reference", "DUPLICATE_COLLECTION_REFERENCE", "Collection 引用", issues, {"type": "collections"})
    for definition in definitions:
        selection = {"type": "collection", "id": definition["id"], "revision": definition["revision"]}
        if not definition["metadata"]["name"].strip():
            issues.append(_issue("MISSING_COLLECTION_NAME", "error", "采集名称不能为空。", {**selection, "field": "metadata.name"}))
        if not definition["spec"]["commandTemplate"].strip():
            label = definition["metadata"]["name"] or definition["key"]
            issues.append(
                _issue(
                    "MISSING_COLLECTION_COMMAND",
                    "error",
                    f"采集“{label}”的采集命令不能为空。",
                    {**selection, "field": "spec.commandTemplate"},
                )
            )
        elif "\n" in definition["spec"]["commandTemplate"] or "\r" in definition["spec"]["commandTemplate"]:
            issues.append(
                _issue(
                    "MULTILINE_COLLECTION_COMMAND",
                    "error",
                    f"采集“{definition['metadata']['name'] or definition['key']}”的采集命令必须为单行。",
                    {**selection, "field": "spec.commandTemplate"},
                )
            )
        _append_duplicates(definition["inputs"], "id", "DUPLICATE_COLLECTION_INPUT_ID", "Collection 输入 ID", issues, selection)
        _append_duplicates(definition["inputs"], "key", "DUPLICATE_COLLECTION_INPUT_KEY", "Collection 输入 key", issues, selection)
        _append_missing_names(definition["inputs"], "Collection 输入名称", issues, selection)
        _append_duplicates(definition["outputs"], "id", "DUPLICATE_COLLECTION_OUTPUT_ID", "Collection 输出 ID", issues, selection)
        _append_duplicates(definition["outputs"], "key", "DUPLICATE_COLLECTION_OUTPUT_KEY", "Collection 输出 key", issues, selection)
        _append_missing_names(definition["outputs"], "Collection 输出名称", issues, selection)
        _append_duplicates(definition["spec"]["outputSamples"], "id", "DUPLICATE_COLLECTION_SAMPLE_ID", "回显示例 ID", issues, selection)


def _append_duplicates(items, field, code, label, issues, selection) -> None:
    counts = Counter(str(item.get(field, "")).strip() for item in items)
    for value, count in counts.items():
        if not value or count > 1:
            message = f"{label}不能为空。" if not value else f"{label}“{value}”重复。"
            issues.append(_issue(code, "error", message, selection))


def _append_optional_duplicates(items, field, code, label, issues, selection) -> None:
    counts = Counter(str(item.get(field, "")).strip() for item in items)
    for value, count in counts.items():
        if value and count > 1:
            issues.append(_issue(code, "error", f"{label}“{value}”重复。", selection))


def _append_missing_names(items, label, issues, selection) -> None:
    for item in items:
        if not str(item.get("name", "")).strip():
            issues.append(_issue("MISSING_PARAMETER_NAME", "error", f"{label}不能为空。", selection))


def _validate_step(step, definitions, node_by_id, role_ids, workflow_input_ids, workflow_input_keys, issues) -> None:
    selection = {"type": "step", "id": step["id"]}
    step_input_ids = {item["parameter"]["id"] for item in step["inputs"]}
    step_input_keys = {item["parameter"]["key"].strip() for item in step["inputs"] if item["parameter"]["key"].strip()}
    call_by_id = {item["id"]: item for item in step["collectionCalls"]}
    unscoped_outputs: dict[str, str] = {}
    for call in step["collectionCalls"]:
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
        call_label = _call_label(call, definition) if definition else call["name"] or "未命名采集"
        if call["sampleCount"] < 1:
            issues.append(_issue("INVALID_SAMPLE_COUNT", "error", f"采集“{call_label}”的样本数量必须大于零。", selection))
        if definition is None:
            issues.append(_issue("BROKEN_REFERENCE", "error", f"采集“{call_label}”引用的定义版本不存在。", selection))
            continue
        if call.get("deviceRoleId") and call["deviceRoleId"] not in role_ids:
            issues.append(_issue("BROKEN_REFERENCE", "error", f"采集“{call['name']}”引用的设备角色不存在。", selection))
        for parameter in definition["inputs"]:
            binding = call["inputBindings"].get(parameter["id"])
            if parameter["required"] and not _binding_has_value(binding):
                issues.append(_issue("MISSING_REQUIRED_BINDING", "error", f"采集“{call_label}”尚未绑定必填参数“{parameter['name']}”。", selection))
            if binding:
                _validate_binding(binding, workflow_input_ids, step_input_ids, call_by_id, definitions, issues, selection)
        if not call["key"].strip():
            _validate_unscoped_outputs(
                call=call,
                definition=definition,
                names=unscoped_outputs,
                reserved=workflow_input_keys | step_input_keys,
                issues=issues,
                selection=selection,
            )
    for transition in step["topology"]:
        target = node_by_id.get(transition["target"]["id"])
        if target is None:
            issues.append(_issue("BROKEN_REFERENCE", "error", f"步骤“{step['name']}”存在无效跳转目标。", selection))


def _validate_unscoped_outputs(*, call, definition, names, reserved, issues, selection) -> None:
    for output in definition["outputs"]:
        key = output["key"].strip()
        if not key:
            continue
        if key in reserved or key in names:
            issues.append(
                _issue(
                    "UNSCOPED_OUTPUT_CONFLICT",
                    "error",
                    f"采集“{_call_label(call, definition)}”直接暴露的输出字段“{key}”与当前步骤字段冲突，请填写调用 key 作为命名空间。",
                    selection,
                )
            )
        names[key] = call["id"]


def _call_label(call, definition) -> str:
    return call["name"].strip() or definition["metadata"]["name"].strip() or definition["key"]


def _validate_binding(binding, workflow_inputs, step_inputs, calls, definitions, issues, selection) -> None:
    kind = binding["kind"]
    ref = binding["reference"]
    valid = kind == "literal"
    if kind == "workflow_input":
        valid = ref.get("input_id") in workflow_inputs
    elif kind == "step_input":
        valid = ref.get("input_id") in step_inputs
    elif kind == "collection_output":
        call = calls.get(ref.get("call_id"))
        definition = definitions.get((call["definition"]["id"], call["definition"]["revision"])) if call else None
        valid = bool(definition and any(item["id"] == ref.get("output_id") for item in definition["outputs"]))
    if not valid:
        issues.append(_issue("BROKEN_REFERENCE", "error", f"参数绑定类型“{kind}”的引用无效。", selection))


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


def _issue(code: str, severity: str, message: str, selection: dict[str, str]) -> dict[str, Any]:
    suffix = selection.get("id", selection["type"])
    return {"id": f"{code.lower()}-{suffix}", "code": code, "severity": severity, "message": message, "selection": selection}
