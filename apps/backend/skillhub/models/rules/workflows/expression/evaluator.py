from __future__ import annotations

import ast
from typing import Any

from .checker import validate_expression
from .registry import FUNCTIONS

_BUILTINS = {
    name: value
    for name, value in {
        "len": len,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
        "sorted": sorted,
        "abs": abs,
        "round": round,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
    }.items()
}


class AttrMapping(dict):
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name not in self:
            raise AttributeError(name)
        return self[name]


def evaluate_expression(
    source: str,
    *,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    config: dict[str, Any] | None = None,
    functions: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Evaluate a validated expression with trusted values and no resource budget."""
    function_catalog = functions or FUNCTIONS
    result = validate_expression(source, {"inputs": {}, "outputs": {}, "config": {}}, function_catalog)
    blocking = [
        item
        for item in result["diagnostics"]
        if item["code"].startswith("FORBIDDEN") or item["code"].startswith("UNREGISTERED") or item["code"] in {"PRIVATE_ACCESS", "UNSUPPORTED_EXPRESSION", "CONFIG_STRING_SUBSCRIPT_FORBIDDEN"}
    ]
    if blocking:
        raise ValueError(blocking[0]["message"])
    tree = ast.parse(source, mode="eval")
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        registered = function_catalog.get(call.func.id)
        if registered is not None and "isBuiltin" in registered and not registered.get("isBuiltin", False):
            raise ValueError(f"函数“{call.func.id}”已注册但自定义函数暂不支持运行。")
        if call.func.id not in _BUILTINS:
            raise ValueError(f"函数“{call.func.id}”已注册但自定义函数暂不支持运行。")
    return eval(compile(tree, "<workflow-expression>", "eval"), {"__builtins__": _BUILTINS}, {"inputs": _wrap(inputs), "outputs": _wrap(outputs), "config": _wrap(config or {})})


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrMapping({key: _wrap(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value
