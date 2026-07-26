from __future__ import annotations

import ast
from typing import Any

from .checker import validate_expression

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


def evaluate_expression(source: str, *, inputs: dict[str, Any], outputs: dict[str, Any]) -> Any:
    """Evaluate a validated expression with trusted values and no resource budget."""
    result = validate_expression(source, {"inputs": {}, "outputs": {}})
    blocking = [
        item
        for item in result["diagnostics"]
        if item["code"].startswith("FORBIDDEN") or item["code"].startswith("UNREGISTERED") or item["code"] in {"PRIVATE_ACCESS", "UNSUPPORTED_EXPRESSION"}
    ]
    if blocking:
        raise ValueError(blocking[0]["message"])
    tree = ast.parse(source, mode="eval")
    return eval(compile(tree, "<workflow-expression>", "eval"), {"__builtins__": _BUILTINS}, {"inputs": _wrap(inputs), "outputs": _wrap(outputs)})


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrMapping({key: _wrap(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value
