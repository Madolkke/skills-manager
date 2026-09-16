"""为 Agent 补全全部表达式诊断及字段内 UTF-16 位置。"""

from copy import deepcopy
from typing import Any

from .expression import validate_binding_expression, validate_expression
from .expression.checker_ast import utf16_length
from .expression.environment import (
    binding_expression_environment,
    conclusion_scope_steps,
    expression_scope_steps,
    project_workflow_expression_environment,
)
from .templates import validate_template
from .validation import _assign_issue_ids


def supplement_expression_diagnostics(document: dict, validation: dict, functions: dict) -> dict[str, list[dict[str, Any]]]:
    """补齐遗漏诊断；既有严重度保持不变，新诊断沿用 checker 严重度。"""
    issues = deepcopy(validation["errors"] + validation["warnings"])
    workflow = document["workflow"]
    nodes = workflow["nodes"]
    definitions = {(item["id"], item["revision"]): item for item in document["collectionSnapshots"]}
    inputs = {item["key"].strip(): item["schema"] for item in workflow["inputs"] if item["key"].strip()}
    roles = workflow["deviceRoles"]
    used: set[int] = set()

    def append(diagnostics, selection):
        """按出现次数匹配既有诊断，避免同字段多个位置被合并丢失。"""
        for diagnostic in diagnostics:
            existing = next((index for index, item in enumerate(issues)
                             if index not in used and item["selection"] == selection
                             and item["code"] == diagnostic["code"] and item["message"] == diagnostic["message"]), None)
            if existing is None:
                issues.append({**diagnostic, "selection": selection, "id": ""})
                used.add(len(issues) - 1)
            else:
                issues[existing].update(start=diagnostic["start"], end=diagnostic["end"])
                used.add(existing)

    for node in nodes:
        conclusion = node.get("nodeType") == "conclusion"
        scope = conclusion_scope_steps(nodes, node["id"]) if conclusion else expression_scope_steps(nodes, node["id"])
        environment = project_workflow_expression_environment(scope, definitions, inputs, roles)
        selection = {"type": "conclusion" if conclusion else "step", "id": node["id"]}
        if conclusion:
            for field in ("rootCause", "repairRecommendation"):
                append(validate_template(node.get(field, ""), environment, functions), {**selection, "field": field})
            continue
        for transition in node["topology"]:
            location = {**selection, "section": "paths", "itemId": transition["id"]}
            append(validate_expression(transition["conditionExpression"], environment, functions)["diagnostics"],
                   {**location, "field": "conditionExpression"})
            append(validate_template(transition["conditionText"], environment, functions), {**location, "field": "conditionText"})
        for call in node["collectionCalls"]:
            reference = call["definition"]
            definition = definitions.get((reference["id"], reference["revision"]))
            if definition is None:
                continue
            environment = binding_expression_environment(nodes, node["id"], call["id"], definitions, inputs, roles)
            parameter_ids = {parameter["id"] for parameter in definition["inputs"]}
            for input_id, binding in call["inputBindings"].items():
                if input_id not in parameter_ids:
                    source = binding.get("expression") or ""
                    append([{"code": "BROKEN_REFERENCE", "severity": "error",
                             "message": f"参数绑定引用的采集输入不存在：{input_id}", "start": 0, "end": utf16_length(source)}],
                           {**selection, "section": "collections", "itemId": call["id"], "field": f"binding.{input_id}"})
            for parameter in definition["inputs"]:
                binding = call["inputBindings"].get(parameter["id"], {})
                if binding.get("kind") != "expression":
                    continue
                source = binding.get("expression", "")
                location = {**selection, "section": "collections", "itemId": call["id"], "field": f"binding.{parameter['id']}"}
                append(validate_binding_expression(source, environment, parameter["schema"], functions)["diagnostics"], location)
                for item in issues:
                    if item["selection"] == location and item["code"] in {"EMPTY_BINDING_EXPRESSION", "INCOMPATIBLE_BINDING_SCHEMA"}:
                        item.update(start=0, end=utf16_length(source))
    _assign_issue_ids(issues)
    return {"errors": [item for item in issues if item["severity"] == "error"],
            "warnings": [item for item in issues if item["severity"] == "warning"]}
