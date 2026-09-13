"""全局函数调用的参数校验。"""
import ast
from typing import Any

from .types import TypeSpec, type_spec_assignable_to_schema


def validate_call_arguments(checker, node: ast.Call, signature: dict[str, Any]) -> None:
    """按持久化顺序检查自定义声明，内置调用保留历史兼容行为。"""
    if signature.get("legacyBuiltin"):
        return
    schema = signature.get("parameterSchema", {})
    # Legacy in-process signatures only describe abstract types.  They do
    # not carry stable parameter names, so keep their historical arity
    # behavior and apply named-argument checks to database-backed schemas.
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        return
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    names = list(schema.get("x-parameter-order", properties))
    if len(node.args) > len(names):
        checker.warn(node, "FUNCTION_TOO_MANY_ARGUMENTS", "函数调用位置参数数量超过声明数量。")
    seen = set(names[: len(node.args)])
    for index, argument in enumerate(node.args):
        if index < len(names) and isinstance(properties.get(names[index]), dict) and not _schema_accepts_type(properties[names[index]], checker.infer(argument)):
            checker.warn(argument, "FUNCTION_ARGUMENT_TYPE_MISMATCH", f"参数“{names[index]}”的类型与函数声明不兼容。")
    for keyword_node in node.keywords:
        if keyword_node.arg is None or keyword_node.arg not in names:
            checker.warn(keyword_node, "FUNCTION_UNKNOWN_KEYWORD", "函数调用包含未声明的关键字参数。")
        elif keyword_node.arg in seen:
            checker.warn(keyword_node, "FUNCTION_DUPLICATE_ARGUMENT", "函数参数被重复提供。")
        else:
            seen.add(keyword_node.arg)
            if isinstance(properties.get(keyword_node.arg), dict) and not _schema_accepts_type(properties[keyword_node.arg], checker.infer(keyword_node.value)):
                checker.warn(keyword_node.value, "FUNCTION_ARGUMENT_TYPE_MISMATCH", f"参数“{keyword_node.arg}”的类型与函数声明不兼容。")
    required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
    for missing in sorted(required - seen):
        checker.warn(node, "FUNCTION_REQUIRED_ARGUMENT", f"函数缺少必填参数“{missing}”。")


def _schema_accepts_type(schema: dict[str, Any], actual: TypeSpec) -> bool:
    """沿用主分支类型兼容规则，未知类型留待运行值确认。"""
    return actual.kind == "any" or type_spec_assignable_to_schema(actual, schema)
