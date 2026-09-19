"""读取离线表达式声明；不连接数据库，不加载或执行函数体。"""
from __future__ import annotations

import json
import keyword
from copy import deepcopy
from pathlib import Path


def read_contract(path: Path | None) -> tuple[dict, dict]:
    """默认复用仓库内置规则，显式文件包括空目录均完整替代默认目录。"""
    from skillhub.models.operations.expression_functions import _validate_schema
    from skillhub.models.rules.workflows.expression.registry import FUNCTIONS

    info = {
        "source": str(path.resolve()) if path else "repository-builtins",
        "contractVersion": 1,
        "notice": "离线声明不能证明目标平台仍启用这些函数；不执行函数体。",
    }
    if path is None:
        return deepcopy(FUNCTIONS), info
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or type(raw.get("contractVersion")) is not int or raw["contractVersion"] != 1:
        raise ValueError("表达式契约必须为 contractVersion=1 的对象。")
    if raw.get("language") != "python-eval" or not isinstance(raw.get("functions"), dict):
        raise ValueError("表达式契约必须包含 language=python-eval 和 functions 对象。")
    functions = {}
    for name, item in raw["functions"].items():
        if not name.isidentifier() or name.startswith("_") or keyword.iskeyword(name) or not isinstance(item, dict):
            raise ValueError(f"非法函数声明：{name}")
        if item.get("name", name) != name:
            raise ValueError(f"函数名称与目录 Key 不一致：{name}")
        for flag in ("enabled", "isBuiltin", "legacyBuiltin"):
            if flag in item and type(item[flag]) is not bool:
                raise ValueError(f"{name}.{flag} 必须是布尔值。")
        builtin = item.get("isBuiltin", item.get("legacyBuiltin", False))
        if item.get("legacyBuiltin") and not builtin:
            raise ValueError(f"函数内置标记冲突：{name}")
        if builtin and name not in FUNCTIONS:
            raise ValueError(f"未知内置函数：{name}")
        schemas = {}
        for field in ("parameterSchema", "returnSchema"):
            if field in item or not builtin:
                schemas[field] = _validate_schema(
                    item.get(field), root_object=field == "parameterSchema", label=f"{name}.{field}",
                    identifier_properties=field == "parameterSchema",
                )
        if not item.get("enabled", True):
            continue
        if builtin:
            functions[name] = deepcopy(FUNCTIONS[name])
        else:
            parameter_schema = schemas["parameterSchema"]
            functions[name] = {
                **schemas,
                "parameters": list(parameter_schema.get("x-parameter-order", parameter_schema["properties"])),
                "returns": schemas["returnSchema"]["type"],
            }
    return functions, info
