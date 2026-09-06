import ast
import re
from collections.abc import Mapping
from typing import Any

from skillhub.models.errors import InvariantError

_OUTPUT_PATH_RE = re.compile(
    r"\boutputs(?P<tail>(?:(?:\s*\.\s*[A-Za-z_]\w*)|(?:\s*\[\s*['\"][^'\"]+['\"]\s*\]))+)"
)


def _validate_source_expression_references(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> None:
    """Reject source updates that invalidate condition/script output paths."""
    workflow = document.get("workflow") if isinstance(document.get("workflow"), Mapping) else {}
    source_id = str(source_call.get("id", ""))
    step = next(
        (
            node
            for node in workflow.get("nodes", [])
            if isinstance(node, Mapping)
            and any(
                isinstance(call, Mapping) and str(call.get("id", "")) == source_id
                for call in node.get("collectionCalls", [])
            )
        ),
        None,
    )
    if step is None:
        return
    call_key = str(source_call.get("key", "")).strip()
    old_outputs = {
        str(item.get("key", "")).strip(): item.get("schema", {})
        for item in current.get("outputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    new_outputs = {
        str(item.get("key", "")).strip(): item.get("schema", {})
        for item in desired.get("outputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    for text in _source_expression_texts(step):
        for path in _extract_output_paths(text):
            reference = _source_output_reference(path, call_key=call_key)
            if reference is None:
                continue
            output_key, nested = reference
            if output_key not in old_outputs:
                continue
            if output_key not in new_outputs:
                raise InvariantError(f"系统命令同步会移除表达式引用的输出“{output_key}”。")
            old_schema = _schema_at_path(old_outputs[output_key], nested)
            new_schema = _schema_at_path(new_outputs[output_key], nested)
            if old_schema is None or new_schema is None:
                raise InvariantError(f"系统命令同步会使表达式引用的输出路径失效: outputs.{output_key}")
            old_type = old_schema.get("type") if isinstance(old_schema, Mapping) else None
            new_type = new_schema.get("type") if isinstance(new_schema, Mapping) else None
            if old_type and new_type and old_type != new_type:
                raise InvariantError(f"系统命令同步会改变表达式引用输出“{output_key}”的类型。")


def _source_output_reference(
    path: tuple[str, ...],
    *,
    call_key: str,
) -> tuple[str, tuple[str, ...]] | None:
    """将 ``outputs`` AST 路径解码为当前 Call 的输出字段和子路径。

    Keyed 多次采集的数组索引在 AST 中统一表示为 ``*``，因此
    ``outputs.call[0].status`` 和 ``outputs.call[index].status`` 都映射到
    输出字段 ``status``，而不是把索引误识别为字段名。
    """
    if not path:
        return None
    if call_key:
        if path[0] != call_key or len(path) < 2:
            return None
        # ``outputs.<callKey>[index].<outputKey>...``
        if path[1] == "*":
            if len(path) < 3:
                return None
            return path[2], path[3:]
        # ``outputs.<callKey>.<outputKey>...``
        return path[1], path[2:]
    # Direct output: an index belongs to the output's own schema.
    return path[0], path[1:]


def _source_expression_texts(step: Mapping[str, Any]) -> list[str]:
    values = [
        str(item.get("conditionExpression", ""))
        for item in step.get("topology", [])
        if isinstance(item, Mapping) and str(item.get("conditionExpression", "")).strip()
    ]
    script = step.get("script")
    if isinstance(script, Mapping) and str(script.get("source", "")).strip():
        values.append(str(script["source"]))
    return values


def _extract_output_paths(text: str) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for mode in ("eval", "exec"):
        try:
            tree = ast.parse(text, mode=mode)
        except (SyntaxError, ValueError):
            continue
        method_attributes = {
            id(item.func)
            for item in ast.walk(tree)
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
        }
        for node in ast.walk(tree):
            # The attribute naming a method (for example ``lower`` in
            # ``outputs.status.lower()``) is not an output property.  The
            # receiver path is still visited separately and retained.
            if isinstance(node, ast.Attribute) and id(node) in method_attributes:
                continue
            path = _ast_output_path(node)
            if path:
                paths.add(path)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                receiver = _ast_output_path(node.func.value)
                if receiver is not None:
                    paths.add((*receiver, node.args[0].value))
    for match in _OUTPUT_PATH_RE.finditer(text):
        tail = match.group("tail")
        tail_start = match.start("tail")
        parts: list[str] = []
        segments = list(
            re.finditer(
                r"\.\s*([A-Za-z_]\w*)|\[\s*['\"]([^'\"]+)['\"]\s*\]",
                tail,
            )
        )
        for segment in segments:
            # In the non-Python fallback, stop at the first method call.  This
            # keeps ``outputs.status`` while excluding ``.lower`` and any
            # properties accessed on the method result.
            if re.match(r"\s*\(", text[tail_start + segment.end() :]):
                break
            parts.append(segment.group(1) or segment.group(2))
        if parts:
            paths.add(tuple(parts))
    return paths


def _ast_output_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return () if node.id == "outputs" else None
    if isinstance(node, ast.Attribute):
        parent = _ast_output_path(node.value)
        return None if parent is None else (*parent, node.attr)
    if isinstance(node, ast.Subscript):
        parent = _ast_output_path(node.value)
        if parent is None:
            return None
        value = node.slice
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return (*parent, value.value)
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            return (*parent, "*")
        # Negative indexes are represented as ``UnaryOp(USub, Constant)``;
        # dynamic indexes and slices have the same schema meaning as any
        # other array element and therefore use the wildcard component.
        if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)):
            return (*parent, "*")
        if isinstance(value, ast.Slice):
            return (*parent, "*")
        return (*parent, "*")
    return None


def _schema_at_path(schema: Any, path: tuple[str, ...]) -> Mapping[str, Any] | None:
    current = schema if isinstance(schema, Mapping) else None
    for component in path:
        if current is None:
            return None
        if current.get("type") == "array":
            current = current.get("items") if component == "*" else None
            continue
        if current.get("type") != "object":
            return None
        properties = current.get("properties")
        if isinstance(properties, Mapping) and component in properties:
            current = properties[component]
        elif current.get("additionalProperties") is True:
            return {"type": None}
        else:
            return None
    return current


