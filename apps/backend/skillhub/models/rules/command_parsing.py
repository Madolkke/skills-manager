"""命令解析候选选择与结果诊断；不读写数据库。"""
from typing import Any

from skillhub.models.errors import CommandParseError
from skillhub.models.rules.workflows.json_schema import value_matches_schema


def command_identity(entry: dict) -> dict[str, str]:
    """投影可公开的命令身份，不返回模板或回显。"""
    return {key: entry[key] for key in ("id", "key", "name", "expression")}


def select_command(entries: list[dict]) -> dict:
    """完整匹配去重后选最高分；同分拒绝，缺模板不参与排序。"""
    exact = {item["id"]: item for item in reversed(entries) if item.get("complete") and (item.get("match") or {}).get("exact")}
    if not exact:
        raise CommandParseError("COMMAND_NOT_FOUND", "没有完整匹配的已启用系统命令。", 404)
    usable = [item for item in exact.values() if str(item.get("ttp") or "").strip()]
    if not usable:
        raise CommandParseError("TTP_TEMPLATE_MISSING", "匹配的系统命令尚未配置 TTP 模板。", 400)
    best = max((item["score"], item.get("consumedTokens", 0)) for item in usable)
    candidates = [item for item in usable if (item["score"], item.get("consumedTokens", 0)) == best]
    if len(candidates) > 1:
        raise CommandParseError("COMMAND_AMBIGUOUS", "多条系统命令具有相同最佳匹配分，请管理员调整规则。", 409,
                                [command_identity(item) for item in sorted(candidates, key=lambda item: item["id"])])
    return candidates[0]


def validate_result(value: Any, schema: dict) -> dict:
    """复用现有类型语义，补充 JSON 路径且不改变实际结果。"""
    warnings: list[dict[str, str]] = []

    def warn(code: str, path: str, message: str) -> None:
        """记录不包含原始回显的诊断。"""
        warnings.append({"code": code, "path": path, "message": message})

    def visit(item: Any, node: dict, path: str) -> None:
        """递归定位类型、必填和额外属性问题。"""
        if value_matches_schema(item, node):
            return
        kind = node.get("type")
        if kind == "object" and isinstance(item, dict):
            properties = node.get("properties", {})
            for key in node.get("required", []):
                if key not in item:
                    warn("SCHEMA_REQUIRED", path + "/" + escape(key), "缺少必填字段。")
            for key, child in item.items():
                child_path = path + "/" + escape(key)
                if key in properties:
                    visit(child, properties[key], child_path)
                elif node.get("additionalProperties") is False:
                    warn("SCHEMA_ADDITIONAL_PROPERTY", child_path, "输出 Schema 不允许此额外字段。")
        elif kind == "array" and isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, node.get("items", {}), f"{path}/{index}")
        else:
            warn("SCHEMA_TYPE_MISMATCH", path, f"结果类型不符合 {kind}。")

    visit(value, schema, "")
    valid = not warnings
    if value in (None, {}, []):
        warn("TTP_EMPTY_RESULT", "", "没有提取到内容，请检查回显与模板。")
    return {"valid": valid, "warnings": warnings}


def escape(key: str) -> str:
    """按 JSON Pointer 编码字段名。"""
    return key.replace("~", "~0").replace("/", "~1")
