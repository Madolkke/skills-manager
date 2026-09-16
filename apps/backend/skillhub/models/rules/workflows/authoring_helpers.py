"""局部编辑的身份定位与内容引用处理，不读取数据库。"""

from copy import deepcopy
from typing import Any

from skillhub.models.entities import new_id
from skillhub.models.errors import InvariantError


def allocate_id(prefix: str, client_ref: str | None, mappings: dict[str, str]) -> str:
    """分配正式 ID，并登记请求内唯一的引用名。"""
    if client_ref and client_ref in mappings:
        raise InvariantError(f"client_ref 重复：{client_ref}")
    result = new_id(prefix)
    if client_ref:
        mappings[client_ref] = result
    return result


def resolve_id(value: str, mappings: dict[str, str]) -> str:
    """解析同批先前创建对象的引用，未声明的引用立即失败。"""
    if not value.startswith("@"):
        return value
    if value[1:] not in mappings:
        raise InvariantError(f"client_ref 尚未定义：{value}")
    return mappings[value[1:]]


def find_item(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    """按稳定 ID 定位对象，不按显示顺序或名称猜测。"""
    item = next((item for item in items if item["id"] == item_id), None)
    if item is None:
        raise InvariantError(f"编辑目标不存在：{item_id}")
    return item


def reorder(items: list[dict[str, Any]], ids: list[str]) -> None:
    """只有包含完整成员且无重复的序列才可用于排序。"""
    if len(ids) != len(set(ids)) or set(ids) != {item["id"] for item in items}:
        raise InvariantError("排序必须包含目标列表的全部 ID，且不能重复。")
    items[:] = [find_item(items, item_id) for item_id in ids]


def patch_fields(item: dict[str, Any], fields: dict[str, Any]) -> None:
    """局部替换明确提供的字段，禁止修改稳定身份。"""
    if {"id", "revision", "forkedFrom", "sourceSystemCommandId"} & fields.keys():
        raise InvariantError("局部更新不能修改对象 ID、版本或来源身份。")
    for key, value in fields.items():
        if key in {"metadata", "script"} and isinstance(value, dict) and isinstance(item.get(key), dict):
            item[key].update(deepcopy(value))
        else:
            item[key] = deepcopy(value)
    if item.get("stepType") == "expression":
        item.pop("script", None)


def resolve_binding(binding: dict[str, Any], mappings: dict[str, str]) -> dict[str, Any]:
    """仅解析绑定引用中的身份字段，表达式和 literal 值保持原文。"""
    result = deepcopy(binding)
    reference = result.get("reference", {})
    for key, value in reference.items():
        if key.endswith("_id") or key.endswith("Id"):
            reference[key] = resolve_id(value, mappings)
    return result


def resolve_fields(fields: dict[str, Any], mappings: dict[str, str]) -> dict[str, Any]:
    """解析作者内容中的结构化身份引用，不遍历替换普通字符串。"""
    result = deepcopy(fields)
    for name in ("definition", "target"):
        if result.get(name):
            result[name]["id"] = resolve_id(result[name]["id"], mappings)
    if result.get("deviceRoleId"):
        result["deviceRoleId"] = resolve_id(result["deviceRoleId"], mappings)
    if result.get("inputBindings") is not None:
        result["inputBindings"] = {
            resolve_id(key, mappings): resolve_binding(value, mappings)
            for key, value in result["inputBindings"].items()
        }
    return result


def assign_parameters(definition: dict[str, Any], mappings: dict[str, str], *, existing: dict[str, Any] | None = None) -> None:
    """为新定义字段分配 ID；复制时允许保留原定义中对应字段的 ID。"""
    for section in ("inputs", "outputs"):
        known = {item["id"] for item in (existing or {}).get(section, [])}
        for item in definition.get(section, []):
            client_ref = item.pop("client_ref", None)
            if item.get("id"):
                if item["id"] not in known:
                    raise InvariantError("新增采集字段不能指定 ID；请使用 client_ref。")
                if client_ref:
                    if client_ref in mappings:
                        raise InvariantError(f"client_ref 重复：{client_ref}")
                    mappings[client_ref] = item["id"]
            else:
                item["id"] = allocate_id("input" if section == "inputs" else "output", client_ref, mappings)
    for query in definition.get("spec", {}).get("queries", []):
        query["outputIds"] = [resolve_id(value, mappings) for value in query.get("outputIds", [])]
