"""把有序局部编辑转换成候选文档，不写数据库或修改调用方数据。"""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.authoring_collections import CandidateCollections
from skillhub.models.rules.workflows.authoring_helpers import allocate_id, find_item, patch_fields, reorder, resolve_binding, resolve_fields, resolve_id
from skillhub.models.rules.workflows.schema import normalize_workflow_document


def build_authoring_candidate(
    document: dict[str, Any], changes: list[dict[str, Any]], *,
    resolve_system_command: Callable[[str, str], dict[str, Any]],
    resolve_collection: Callable[[str, int | None], dict[str, Any]],
) -> dict[str, Any]:
    """应用整批编辑并规范化结构，业务诊断由调用方使用统一校验器产生。"""
    candidate = deepcopy(document)
    mappings: dict[str, str] = {}
    collections = CandidateCollections(candidate, mappings, resolve_system_command, resolve_collection)
    summaries: list[str] = []
    for change in changes:
        _apply_change(candidate["workflow"], change, mappings, collections)
        summaries.append(f"已应用 {change['operation']}")
    collection_changes = collections.finish(candidate)
    return {
        "document": normalize_workflow_document(candidate), "collection_changes": collection_changes,
        "id_mappings": mappings, "summary": summaries,
    }


def _apply_change(workflow: dict[str, Any], change: dict[str, Any], mappings: dict[str, str], collections: CandidateCollections) -> None:
    """按所属对象分派局部操作，步骤内容不通过 metadata 入口修改。"""
    operation = change["operation"]
    kind, action = operation.split(".")
    if kind == "metadata" and action == "update":
        patch_fields(workflow["metadata"], change["fields"])
        return
    if kind in {"input", "role", "node"}:
        key = {"input": "inputs", "role": "deviceRoles", "node": "nodes"}[kind]
        _edit_list(workflow.setdefault(key, []), kind, action, change, mappings)
        if kind == "node" and action == "remove":
            deleted = resolve_id(change["node_id"], mappings)
            for node in workflow["nodes"]:
                if "topology" in node:
                    node["topology"] = [edge for edge in node["topology"] if edge["target"]["id"] != deleted]
        return
    node = find_item(workflow["nodes"], resolve_id(change["node_id"], mappings))
    if node.get("stepType") not in {"expression", "script"}:
        raise InvariantError("仅步骤节点可编辑采集和跳转。")
    if kind == "transition":
        _edit_list(node.setdefault("topology", []), kind, action, change, mappings)
    elif kind == "call":
        _edit_call(node, action, change, mappings, collections)
    elif kind == "binding":
        call = find_item(node.get("collectionCalls", []), resolve_id(change["call_id"], mappings))
        if action == "set":
            input_id = collections.parameter_id(call, change["input_id"])
            call.setdefault("inputBindings", {})[input_id] = resolve_binding(change["binding"], mappings)
        elif action == "remove":
            input_id = resolve_id(change["input_id"], mappings)
            call.setdefault("inputBindings", {}).pop(input_id, None)
        else:
            raise InvariantError(f"未知操作：{operation}")
    else:
        raise InvariantError(f"未知操作：{operation}")


def _edit_list(items: list[dict[str, Any]], kind: str, action: str, change: dict[str, Any], mappings: dict[str, str]) -> None:
    """复用身份定位、局部更新、删除及完整排序语义。"""
    if action == "reorder":
        reorder(items, [resolve_id(value, mappings) for value in change["ids"]])
        return
    if action == "add":
        item: dict[str, Any] = {"id": allocate_id(kind, change.get("client_ref"), mappings)}
        patch_fields(item, resolve_fields(change["fields"], mappings))
        if kind == "node" and "stepType" in item:
            item.setdefault("collectionCalls", [])
            item.setdefault("topology", [])
        items.append(item)
        return
    item = find_item(items, resolve_id(change[f"{kind}_id"], mappings))
    if action == "update":
        patch_fields(item, resolve_fields(change["fields"], mappings))
    elif action == "remove":
        items.remove(item)
    else:
        raise InvariantError(f"未知操作：{kind}.{action}")


def _edit_call(node: dict[str, Any], action: str, change: dict[str, Any], mappings: dict[str, str], collections: CandidateCollections) -> None:
    """将定义的创建/复制与调用编辑组合为同一候选文档。"""
    calls = node.setdefault("collectionCalls", [])
    if action in {"from_system", "create_collection"}:
        reference = collections.create(change)
        fields = {**change["fields"], "definition": reference}
        _edit_list(calls, "call", "add", {**change, "fields": fields}, mappings)
    elif action == "fork_collection":
        call = find_item(calls, resolve_id(change["call_id"], mappings))
        call["definition"] = collections.fork(call, change)
    else:
        _edit_list(calls, "call", action, change, mappings)
        if action in {"add", "update"}:
            call = calls[-1] if action == "add" else find_item(calls, resolve_id(change["call_id"], mappings))
            collections.resolve(call["definition"])
