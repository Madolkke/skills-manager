"""候选采集快照及来源复制，所有解析回调均只读。"""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.authoring_helpers import allocate_id, assign_parameters, patch_fields, resolve_id
from skillhub.models.rules.workflows.command_instances import set_instance_command
from skillhub.models.rules.workflows.schema import normalize_collection_definition


class CandidateCollections:
    """维护待保存的采集变更及精确版本快照，不执行写入。"""

    def __init__(
        self, document: dict[str, Any], mappings: dict[str, str],
        resolve_system_command: Callable[[str, str], dict[str, Any]],
        resolve_collection: Callable[[str, int | None], dict[str, Any]],
    ) -> None:
        """从调用中的现有快照开始建立候选索引。"""
        self.mappings = mappings
        self.resolve_system_command = resolve_system_command
        self.resolve_collection = resolve_collection
        self.snapshots = {(item["id"], item["revision"]): deepcopy(item) for item in document.get("collectionSnapshots", [])}
        self.changes: list[dict[str, Any]] = []

    def resolve(self, reference: dict[str, Any]) -> dict[str, Any]:
        """获取指定精确版本，缺失时由只读回调补齐。"""
        key = (reference["id"], reference["revision"])
        if key not in self.snapshots:
            self.snapshots[key] = normalize_collection_definition(self.resolve_collection(*key))
        definition = self.snapshots[key]
        if (definition["id"], definition["revision"]) != key:
            raise InvariantError("采集解析结果与请求的精确版本不一致。")
        return definition

    def create(self, change: dict[str, Any]) -> dict[str, Any]:
        """从系统来源或自定义内容创建只存在于候选中的定义。"""
        definition_id = allocate_id("collection", change.get("definition_ref"), self.mappings)
        if change["operation"] == "call.from_system":
            definition = deepcopy(self.resolve_system_command(change["command_id"], definition_id))
            definition["id"], definition["revision"] = definition_id, 1
            definition["sourceSystemCommandId"] = change["command_id"]
            definition["inputs"] = []
            definition = set_instance_command(definition, change["command_template"])
        else:
            definition = deepcopy(change["definition"])
            if {"id", "revision", "forkedFrom", "sourceSystemCommandId", "sourceBindingMode"} & definition.keys():
                raise InvariantError("新采集定义不能指定身份或来源。")
            assign_parameters(definition, self.mappings)
            definition.update(id=definition_id, revision=1)
        return self._register("create", definition)

    def fork(self, call: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
        """复制已保存定义，保留原字段 ID，仅解除自动系统来源关系。"""
        source = deepcopy(self.resolve(call["definition"]))
        fields = deepcopy(change["fields"])
        assign_parameters(fields, self.mappings, existing=source)
        definition = deepcopy(source)
        patch_fields(definition, fields)
        definition["forkedFrom"] = deepcopy(call["definition"])
        definition.pop("sourceSystemCommandId", None)
        definition.pop("sourceBindingMode", None)
        definition["id"] = allocate_id("collection", change.get("definition_ref"), self.mappings)
        definition["revision"] = 1
        return self._register("fork", definition)

    def set_command(self, call: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
        """仅重绑定指定调用；命令编辑保留同名输入身份和有效绑定。"""
        source = self.resolve(call["definition"])
        if source["spec"]["collectionType"] != "cli":
            raise InvariantError("只有 CLI 采集可以设置具体命令。")
        definition = set_instance_command(source, change["command_template"])
        definition["forkedFrom"] = deepcopy(call["definition"])
        definition["id"] = allocate_id("collection", change.get("definition_ref"), self.mappings)
        definition["revision"] = 1
        valid_inputs = {item["id"] for item in definition["inputs"]}
        call["inputBindings"] = {key: value for key, value in call.get("inputBindings", {}).items() if key in valid_inputs}
        return self._register("fork", definition)

    def _register(self, operation: str, definition: dict[str, Any]) -> dict[str, Any]:
        """规范化候选定义，并返回供采集调用使用的版本引用。"""
        definition = normalize_collection_definition(definition)
        self.snapshots[(definition["id"], definition["revision"])] = definition
        self.changes.append({"operation": operation, "definition": definition})
        return {"id": definition["id"], "revision": definition["revision"]}

    def finish(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """仅保存最终调用引用的快照和新定义，避免新增后删除留下孤立数据。"""
        references = {
            (call["definition"]["id"], call["definition"]["revision"])
            for node in document["workflow"]["nodes"] for call in node.get("collectionCalls", [])
        }
        document["collectionSnapshots"] = [self.resolve({"id": key[0], "revision": key[1]}) for key in sorted(references)]
        retained = set(references)
        for change in reversed(self.changes):
            definition = change["definition"]
            if (definition["id"], definition["revision"]) in retained and definition.get("forkedFrom"):
                source = definition["forkedFrom"]
                retained.add((source["id"], source["revision"]))
        return [change for change in self.changes if (change["definition"]["id"], change["definition"]["revision"]) in retained]

    def parameter_id(self, call: dict[str, Any], value: str) -> str:
        """绑定通过输入 ID 或已声明的临时引用定位目标。"""
        input_id = resolve_id(value, self.mappings)
        if not any(item["id"] == input_id for item in self.resolve(call["definition"])["inputs"]):
            raise InvariantError(f"采集输入不存在：{input_id}")
        return input_id
