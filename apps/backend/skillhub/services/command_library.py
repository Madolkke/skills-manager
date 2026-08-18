from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from skillhub.models.errors import InvariantError, PermissionDeniedError
from skillhub.models.rules.workflows.schema import CollectionMetadata
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class CommandLibraryService(ServiceBase[SkillHubStore]):
    """命令库查询和系统命令管理服务。"""

    def search(
        self,
        *,
        command: str,
        actor: str,
        include_user: bool = False,
        target_version: str | None = None,
        owner_ref: str | None = None,
        include_system: bool = True,
        include_disabled: bool = False,
        partial: bool = True,
        prefix: bool = True,
    ) -> dict[str, Any]:
        if owner_ref and owner_ref != actor:
            raise PermissionDeniedError("Command library owner does not match the current actor.")
        return {
            "results": self.store.search_command_library(
                query=command,
                actor=actor,
                owner_ref=owner_ref,
                include_system=include_system,
                include_user=include_user,
                include_disabled=include_disabled,
                target_version=target_version,
                partial=partial,
                prefix=prefix,
            )
        }

    def list_system(self) -> dict[str, Any]:
        return {"commands": self.store.list_system_commands()}

    def get_system(self, *, command_id: str) -> dict[str, Any]:
        return self.store.get_system_command(command_id=command_id)

    def create_system(self, *, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        key = payload["key"]
        name = payload.get("name") or (payload.get("metadata") or {}).get("name") or key
        description = payload.get("description") if payload.get("description") is not None else (payload.get("metadata") or {}).get("description", "")
        metadata = _normalize_metadata(payload.get("metadata"), name=name, description=description)
        document = {
            "metadata": metadata,
            "samples": list(payload.get("samples") or []),
            "outputSchema": payload.get("outputSchema") or {},
            "ttp": payload.get("ttp", ""),
        }
        _validate_samples(document["samples"])
        _validate_output_schema(document["outputSchema"])
        return self.store.create_system_command(
            command_id=payload.get("id"),
            key=key,
            name=metadata["name"],
            description=metadata["description"],
            expression=payload["expression"],
            captures=payload.get("captures"),
            metadata=metadata,
            enabled=payload.get("enabled", True),
            document=document,
            actor=actor,
        )

    def update_system(self, *, command_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        changes = {key: value for key, value in payload.items() if value is not None and key not in {"id", "samples", "outputSchema", "ttp"}}
        current = self.store.get_system_command(command_id=command_id)
        raw_metadata = payload.get("metadata") if payload.get("metadata") is not None else current.get("metadata")
        name = payload.get("name") or (raw_metadata or {}).get("name") or current.get("name") or payload.get("key") or current.get("key")
        if "description" in payload and payload.get("description") is not None:
            description = payload["description"]
        elif isinstance(raw_metadata, Mapping) and "description" in raw_metadata:
            description = raw_metadata["description"]
        else:
            description = current.get("description") or ""
        metadata = _normalize_metadata(raw_metadata, name=name, description=description)
        changes["name"] = metadata["name"]
        changes["description"] = metadata["description"]
        changes["metadata"] = metadata
        changes["document"] = {
            "metadata": metadata,
            "samples": list(payload.get("samples", current.get("samples", [])) or []),
            "outputSchema": payload.get("outputSchema", current.get("outputSchema", {})) or {},
            "ttp": payload.get("ttp", current.get("ttp", "")),
        }
        _validate_samples(changes["document"]["samples"])
        _validate_output_schema(changes["document"]["outputSchema"])
        return self.store.update_system_command(command_id=command_id, actor=actor, **changes)

    def delete_system(self, *, command_id: str) -> dict[str, Any]:
        return self.store.delete_system_command(command_id=command_id)


def _validate_output_schema(value: Any) -> None:
    if not isinstance(value, Mapping) or value.get("type") != "object":
        raise InvariantError("系统命令根输出 Schema 必须为 object。")
    properties = value.get("properties")
    required = value.get("required", [])
    additional_properties = value.get("additionalProperties", False)
    if not isinstance(properties, Mapping) or not isinstance(required, list) or not isinstance(additional_properties, bool):
        raise InvariantError("系统命令根输出 Schema 必须包含 properties 对象和 required 数组。")
    if any(not isinstance(name, str) or not name.strip() for name in properties):
        raise InvariantError("系统命令根输出 Schema 属性名不能为空。")
    if any(not isinstance(name, str) for name in required) or len(required) != len(set(required)) or not set(required).issubset(properties):
        raise InvariantError("系统命令根输出 Schema required 必须引用 properties。")
    for schema in properties.values():
        _validate_schema_fragment(schema)


def _validate_samples(value: Any) -> None:
    if not isinstance(value, list):
        raise InvariantError("回显示例必须是数组。")
    for index, sample in enumerate(value, start=1):
        if not isinstance(sample, Mapping):
            raise InvariantError(f"第 {index} 个回显示例必须是对象。")
        name = sample.get("name")
        command = sample.get("command")
        stdout = sample.get("stdout")
        if not isinstance(name, str) or not name.strip() or not isinstance(command, str) or not command.strip() or not isinstance(stdout, str):
            raise InvariantError(f"第 {index} 个回显示例必须包含 name、完整 command 和 stdout 文本。")


def _validate_schema_fragment(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise InvariantError("系统命令输出 Schema 属性必须是对象。")
    schema_type = value.get("type")
    if schema_type not in {"string", "integer", "number", "boolean", "object", "array"}:
        raise InvariantError("系统命令输出 Schema 属性必须声明受支持的 type。")
    if schema_type == "object":
        properties = value.get("properties")
        required = value.get("required", [])
        additional_properties = value.get("additionalProperties", False)
        if not isinstance(properties, Mapping) or not isinstance(required, list) or not isinstance(additional_properties, bool):
            raise InvariantError("对象 Schema 必须包含 properties 对象和 required 数组。")
        if any(not isinstance(name, str) for name in required) or len(required) != len(set(required)) or not set(required).issubset(properties):
            raise InvariantError("对象 Schema required 必须引用 properties。")
        for child in properties.values():
            _validate_schema_fragment(child)
    elif schema_type == "array":
        if "items" not in value:
            raise InvariantError("数组 Schema 必须包含 items。")
        _validate_schema_fragment(value["items"])


def _normalize_metadata(value: Any, *, name: Any, description: Any) -> dict[str, Any]:
    raw = dict(value or {}) if isinstance(value, Mapping) else {}
    raw["name"] = str(name).strip()
    raw["description"] = str(description)
    if not raw["name"]:
        raise InvariantError("系统命令名称不能为空。")
    try:
        return CollectionMetadata.model_validate(raw).model_dump(by_alias=True)
    except ValidationError as exc:
        raise InvariantError("系统命令元数据必须符合 CollectionMetadata 格式。") from exc
