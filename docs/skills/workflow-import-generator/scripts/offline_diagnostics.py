"""将后端诊断定位回可移植 Bundle，并保留表达式字符位置。"""
from __future__ import annotations


def expression_diagnostics(document: dict, functions: dict) -> list[dict]:
    """使用后端作用域和静态检查器收集条件、模板及绑定的原始诊断。"""
    from skillhub.models.rules.workflows.expression import validate_binding_expression, validate_expression
    from skillhub.models.rules.workflows.expression.environment import (
        binding_expression_environment, conclusion_scope_steps, expression_scope_steps,
        project_workflow_expression_environment,
    )
    from skillhub.models.rules.workflows.templates import validate_template

    workflow = document["workflow"]
    nodes, roles = workflow["nodes"], workflow["deviceRoles"]
    definitions = {(d["id"], d["revision"]): d for d in document["collectionSnapshots"]}
    inputs = {p["key"]: p["schema"] for p in workflow["inputs"]}
    result = []
    for node in nodes:
        scope = expression_scope_steps(nodes, node["id"]) if "stepType" in node else conclusion_scope_steps(nodes, node["id"])
        environment = project_workflow_expression_environment(scope, definitions, inputs, roles)
        fields = []
        if "stepType" in node:
            for transition in node["topology"]:
                selection = {"type": "step", "id": node["id"], "section": "paths", "itemId": transition["id"]}
                fields.extend((
                    (transition["conditionExpression"], False, {**selection, "field": "conditionExpression"}),
                    (transition["conditionText"], True, {**selection, "field": "conditionText"}),
                ))
            for call in node["collectionCalls"]:
                reference = call["definition"]
                definition = definitions[(reference["id"], reference["revision"])]
                env = binding_expression_environment(nodes, node["id"], call["id"], definitions, inputs, roles)
                for parameter in definition["inputs"]:
                    binding = call["inputBindings"].get(parameter["id"], {})
                    if binding.get("kind") != "expression":
                        continue
                    checked = validate_binding_expression(binding.get("expression", ""), env, parameter["schema"], functions)
                    selection = {"type": "step", "id": node["id"], "section": "collections", "itemId": call["id"],
                                 "field": f"inputBindings.{parameter['id']}"}
                    result.extend({**d, "selection": selection} for d in checked["diagnostics"])
        else:
            fields.extend((node[field], True, {"type": "conclusion", "id": node["id"], "field": field})
                          for field in ("rootCause", "repairRecommendation"))
        for source, template, selection in fields:
            diagnostics = validate_template(source, environment, functions) if template else validate_expression(source, environment, functions)["diagnostics"]
            result.extend({**d, "selection": selection} for d in diagnostics)
    return result


def locate(issue: dict, bundle: dict) -> dict:
    """附加 Bundle 定位，临时 Collection 身份使用 localId，原始 selection 不丢弃。"""
    selection = issue.get("selection", {})
    location = {"field": selection.get("field", "")}
    kind = selection.get("type")
    if kind == "collection":
        location.update(localId=selection.get("id"), itemId=selection.get("itemId"))
    elif kind in {"step", "conclusion"}:
        location["nodeId"] = selection.get("id")
        item_id = selection.get("itemId")
        if selection.get("section") == "collections":
            location["callId"] = item_id
            node = next((n for n in bundle["workflow"]["nodes"] if n["id"] == location["nodeId"]), {})
            call = next((c for c in node.get("collectionCalls", []) if c["id"] == item_id), {})
            location["localId"] = call.get("definitionLocalId")
        elif selection.get("section") == "paths":
            location["transitionId"] = item_id
    else:
        location.update(section=kind, itemId=selection.get("itemId"))
    return {**issue, "location": {key: value for key, value in location.items() if value is not None}}
