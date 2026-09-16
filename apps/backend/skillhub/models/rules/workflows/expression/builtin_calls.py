"""内置函数静态签名；仅检查声明类型，不执行作者表达式。"""
import ast
from typing import Any

from .types import ANY, STRING, TypeSpec, array, union

# 参数名沿用已发布目录。? 表示可省略，* 表示仅限关键字。
BUILTIN_PARAMETERS = {
    "len": [("value", "sized")],
    "min": [("iterable", "iterable"), ("default", "any?*"), ("key", "none?*")],
    "max": [("iterable", "iterable"), ("default", "any?*"), ("key", "none?*")],
    "sum": [("iterable", "numeric-array"), ("start", "number?")],
    "any": [("iterable", "iterable")],
    "all": [("iterable", "iterable")],
    "sorted": [("iterable", "iterable"), ("key", "none?*"), ("reverse", "boolean?*")],
    "abs": [("value", "number")],
    "round": [("value", "number"), ("ndigits", "integer?")],
    "str": [("value", "any?")],
    "int": [("value", "convertible?"), ("base", "integer?")],
    "float": [("value", "convertible?")],
    "bool": [("value", "any?")],
    "list": [("iterable", "iterable?")],
}


def builtin_signature(name: str) -> dict[str, Any]:
    """提供由校验规则生成的参数提示，避免旧种子 Schema 误报泛型。"""
    params = BUILTIN_PARAMETERS[name]
    display = [f"{key}: {kind.rstrip('?*')}{' = …' if '?' in kind else ''}" for key, kind in params]
    if name in {"min", "max"}:
        display[0] = "iterable<T> | value1, value2, ..."
    return {"legacyBuiltin": True, "parameters": [key for key, _ in params], "signatureDisplay": ", ".join(display)}


def validate_builtin_call(checker, node: ast.Call, name: str) -> None:
    """检查参数绑定、数量和可判定的不兼容类型，未知类型保持宽容。"""
    params = BUILTIN_PARAMETERS[name]
    positional = [(key, kind) for key, kind in params if '*' not in kind]
    variadic = name in {"min", "max"} and len(node.args) >= 2
    seen = set()
    if not variadic and len(node.args) > len(positional):
        checker.warn(node, "FUNCTION_TOO_MANY_ARGUMENTS", "函数调用位置参数数量超过声明数量。")
    for index, argument in enumerate(node.args):
        if variadic:
            seen.add("iterable")
            _check_type(checker, argument, "comparable", "value")
        elif index < len(positional):
            key, kind = positional[index]
            seen.add(key)
            _check_type(checker, argument, kind, key)
    for keyword in node.keywords:
        key = keyword.arg
        if key not in dict(params) or (variadic and key == "default"):
            checker.warn(keyword, "FUNCTION_UNKNOWN_KEYWORD", "函数调用包含未声明或当前重载不支持的关键字参数。")
        elif key in seen:
            checker.warn(keyword, "FUNCTION_DUPLICATE_ARGUMENT", "函数参数被重复提供。")
        else:
            seen.add(key)
            _check_type(checker, keyword.value, dict(params)[key], key)
    for key, kind in params:
        if '?' not in kind and key not in seen:
            checker.warn(node, "FUNCTION_REQUIRED_ARGUMENT", f"函数缺少必填参数“{key}”。")
    if name in {"min", "max"}:
        values = [checker.infer(value) for value in node.args] if variadic else []
        kinds = {value.kind for value in values if value.kind != "any"}
        if 'string' in kinds and kinds - {'string'}:
            checker.warn(node, "FUNCTION_ARGUMENT_TYPE_MISMATCH", "min/max 的多个实参必须具有可比较的类型。")
    if name == "int" and (len(node.args) > 1 or any(item.arg == 'base' for item in node.keywords)):
        value = node.args[0] if node.args else next((item.value for item in node.keywords if item.arg == 'value'), None)
        if value is None:
            checker.warn(node, "FUNCTION_REQUIRED_ARGUMENT", "指定 base 时必须提供 value。")
        else:
            _check_type(checker, value, "string", "value（指定 base 时）")


def _check_type(checker, node: ast.AST, kind: str, name: str) -> None:
    """复用表达式类型推断，避免检查运行值或实际转换。"""
    if not _accepts(checker.infer(node), kind.rstrip('?*')):
        checker.warn(node, "FUNCTION_ARGUMENT_TYPE_MISMATCH", f"参数“{name}”的类型与内置函数声明不兼容。")


def _accepts(actual: TypeSpec, expected: str) -> bool:
    """泛型容器允许任意元素；数值聚合单独验证元素。"""
    if actual.kind == 'any' or expected == 'any':
        return True
    if actual.kind == 'union':
        return all(_accepts(option, expected) for option in actual.options)
    if expected in {'iterable', 'sized'}:
        return actual.kind in {'array', 'object', 'string'}
    if expected == 'numeric-array':
        return actual.kind == 'array' and _accepts(actual.item or ANY, 'number')
    kinds = {
        'number': {'number', 'integer'}, 'convertible': {'string', 'number', 'integer', 'boolean'},
        'comparable': {'string', 'number', 'integer', 'boolean'},
    }
    return actual.kind in kinds.get(expected, {expected})


def builtin_return_type(checker, node: ast.Call, name: str) -> TypeSpec | None:
    """从实际实参推断泛型，包括关键字调用和 min/max 多参数重载。"""
    if name not in {'min', 'max', 'sorted', 'list'}:
        return None
    if name in {'min', 'max'} and len(node.args) >= 2:
        return union(*(checker.infer(item) for item in node.args))
    source = node.args[0] if node.args else next((item.value for item in node.keywords if item.arg == 'iterable'), None)
    actual = checker.infer(source) if source else ANY
    item = STRING if actual.kind in {'string', 'object'} else actual.item or ANY
    if name in {'sorted', 'list'}:
        return array(item)
    default = next((keyword.value for keyword in node.keywords if keyword.arg == 'default'), None)
    return union(item, checker.infer(default)) if default else item
