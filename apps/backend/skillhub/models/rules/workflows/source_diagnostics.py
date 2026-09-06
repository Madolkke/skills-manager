from collections import Counter

from skillhub.models.errors import InvariantError

from .expression import validate_binding_expression, validate_expression
from .expression.environment import (
    binding_expression_environment,
    conclusion_scope_steps,
    expression_scope_steps,
    project_workflow_expression_environment,
)
from .source_references import _extract_output_paths, _schema_at_path, _source_output_reference
from .templates import validate_template


def validate_source_diagnostics(original, candidate):
    """只阻止来源更新新增的引用诊断，保留其他已有草稿问题。"""
    before = _diagnostics(original)
    after = _diagnostics(candidate)
    added = after - before
    if added:
        location, _, message = next(iter(added))
        raise InvariantError(f"系统命令同步会使表达式引用或输出作用域失效: {location}: {message}")
    _validate_referenced_types(original, candidate)


def _diagnostics(document):
    """检查所有表达式入口，按字段位置保留诊断计数。"""
    workflow = document.get("workflow", {})
    nodes = workflow.get("nodes", [])
    definitions = {(value["id"], value["revision"]): value for value in document.get("collectionSnapshots", [])}
    inputs = {value["key"].strip(): value["schema"] for value in workflow.get("inputs", []) if value.get("key", "").strip()}
    roles = workflow.get("deviceRoles", [])
    all_calls = {call["id"]: call for node in nodes for call in node.get("collectionCalls", [])}
    result = Counter()

    def add(location, diagnostics):
        """同一已有错误不会阻断无关更新。"""
        for item in diagnostics:
            result[(location, item["code"], item["message"])] += 1

    for node in nodes:
        node_id = node.get("id", "")
        scope = conclusion_scope_steps(nodes, node_id) if node.get("nodeType") == "conclusion" else expression_scope_steps(nodes, node_id)
        environment = project_workflow_expression_environment(scope, definitions, inputs, roles)
        for key in _conflicts(scope, definitions, inputs):
            add(node_id, [{"code": "OUTPUT_CONFLICT", "message": key}])
        for transition in node.get("topology", []):
            location = f"{node_id}.{transition.get('id', '')}"
            expression = transition.get("conditionExpression", "")
            if expression.strip():
                add(location + ".conditionExpression", validate_expression(expression, environment)["diagnostics"])
            add(location + ".conditionText", validate_template(transition.get("conditionText", ""), environment))
        for field in ("rootCause", "repairRecommendation"):
            if node.get("nodeType") == "conclusion":
                add(node_id + "." + field, validate_template(node.get(field, ""), environment))
        for call in node.get("collectionCalls", []):
            reference = call.get("definition", {})
            definition = definitions.get((reference.get("id"), reference.get("revision")), {})
            parameters = {item["id"]: item for item in definition.get("inputs", [])}
            binding_environment = binding_expression_environment(nodes, node_id, call["id"], definitions, inputs, roles)
            for input_id, binding in call.get("inputBindings", {}).items():
                location = f"{node_id}.{call['id']}.{input_id}"
                if input_id not in parameters:
                    add(location, [{"code": "MISSING_INPUT", "message": "输入定义不存在"}])
                if binding.get("kind") == "collection_output" and input_id in parameters:
                    add(location, _output_binding_diagnostics(binding, parameters[input_id], all_calls, definitions))
                if binding.get("kind") != "expression" or input_id not in parameters:
                    continue
                checked = validate_binding_expression(binding.get("expression", ""), binding_environment, parameters[input_id]["schema"])
                location = f"{node_id}.{call['id']}.{input_id}"
                add(location, checked["diagnostics"])
                if not checked["diagnostics"] and not checked["assignable"]:
                    add(location, [{"code": "BINDING_TYPE", "message": "表达式结果与输入 Schema 不兼容"}])
        script = node.get("script") or {}
        if script.get("source"):
            for path in _extract_output_paths(script["source"]):
                schema = _script_schema(scope, definitions, path)
                if schema is None:
                    add(node_id + ".script", [{"code": "SCRIPT_OUTPUT_PATH", "message": str(path)}])
    return result


def _output_binding_diagnostics(binding, parameter, calls, definitions):
    """逐条检查输出绑定，防止旧草稿的首个错误掩盖新增断裂。"""
    from .json_schema import schemas_assignable

    reference = binding.get("reference", {})
    source = calls.get(reference.get("call_id"), {})
    definition_ref = source.get("definition", {})
    definition = definitions.get((definition_ref.get("id"), definition_ref.get("revision")), {})
    output = next((item for item in definition.get("outputs", []) if item["id"] == reference.get("output_id")), None)
    if output is None:
        return [{"code": "MISSING_OUTPUT", "message": "绑定的输出不存在"}]
    if not schemas_assignable(output["schema"], parameter["schema"]):
        return [{"code": "OUTPUT_BINDING_TYPE", "message": "输出与输入 Schema 不兼容"}]
    return []


def _conflicts(scope, definitions, inputs):
    """检查候选图中同一可见作用域内的直接输出冲突。"""
    names = Counter()
    for step in scope:
        for call in step.get("collectionCalls", []):
            if call.get("key", "").strip() or call.get("sampleCount", 1) > 1:
                continue
            reference = call.get("definition", {})
            definition = definitions.get((reference.get("id"), reference.get("revision")), {})
            names.update(item["key"] for item in definition.get("outputs", []))
    return {name for name, count in names.items() if count > 1 or name in inputs}


def _script_schema(scope, definitions, path):
    """脚本不能整体按表达式求值，仅解析已存在的输出路径。"""
    for step in scope:
        for call in step.get("collectionCalls", []):
            reference = _source_output_reference(path, call_key=call.get("key", ""))
            if reference is None:
                continue
            key, nested = reference
            definition_ref = call.get("definition", {})
            definition = definitions.get((definition_ref.get("id"), definition_ref.get("revision")), {})
            for output in definition.get("outputs", []):
                if output["key"] == key:
                    return _schema_at_path(output["schema"], nested)
    return None


def _validate_referenced_types(original, candidate):
    """所有已引用路径的明确类型均须保持兼容，包括脚本和模板。"""
    old_types = _referenced_types(original)
    new_types = _referenced_types(candidate)
    for reference, old_type in old_types.items():
        if reference not in new_types:
            raise InvariantError(f"系统命令同步会使表达式引用输出路径失效: {reference[0]}: {reference[1]}")
        new_type = new_types.get(reference)
        if old_type and new_type and old_type != new_type:
            raise InvariantError(f"系统命令同步会改变表达式引用输出的类型: {reference[0]}: {reference[1]}")


def _referenced_types(document):
    """按入口可见性提取真实输出引用，避免无连接节点同名输出误报。"""
    from .expression.environment import binding_scope_calls
    from .templates import iter_template_expressions

    workflow = document.get("workflow", {})
    nodes = workflow.get("nodes", [])
    definitions = {(item["id"], item["revision"]): item for item in document.get("collectionSnapshots", [])}
    result = {}

    def collect(location, text, scope, *, template=False):
        """模板仅分析插值正文，普通文本不属于表达式引用。"""
        sources = [text]
        if template:
            sources = [expression.strip() for expression, _, _ in iter_template_expressions(text)]
        for source in sources:
            for path in _extract_output_paths(source):
                schema = _script_schema(scope, definitions, path)
                if schema is not None:
                    result[(location, path)] = schema.get("type")

    for node in nodes:
        node_id = node.get("id", "")
        scope = conclusion_scope_steps(nodes, node_id) if node.get("nodeType") == "conclusion" else expression_scope_steps(nodes, node_id)
        for transition in node.get("topology", []):
            for field in ("conditionExpression", "conditionText"):
                collect(f"{node_id}.{transition.get('id', '')}.{field}", transition.get(field, ""), scope, template=field == "conditionText")
        if node.get("nodeType") == "conclusion":
            for field in ("rootCause", "repairRecommendation"):
                collect(node_id + "." + field, node.get(field, ""), scope, template=True)
        collect(node_id + ".script", (node.get("script") or {}).get("source", ""), scope)
        for call in node.get("collectionCalls", []):
            visible, _ = binding_scope_calls(nodes, node_id, call["id"])
            binding_scope = [{"collectionCalls": [entry["call"] for entry in visible.values()]}]
            for input_id, binding in call.get("inputBindings", {}).items():
                if binding.get("kind") == "expression":
                    collect(f"{node_id}.{call['id']}.{input_id}", binding.get("expression", ""), binding_scope)
    return result
