"""MCP 局部编辑的内容字段，沿用作者文档的 camelCase 命名。"""

from typing import Annotated, Any, Literal

from pydantic import Field

from skillhub.models.rules.workflows.schema import (
    Binding,
    CollectionMetadata,
    CollectionSpec,
    JsonSchema,
    NodeRef,
    ScriptDraft,
    VersionedRef,
    WorkflowModel,
)


def _omitted_value() -> Any:
    """仅为未提供字段保留占位；边界序列化使用 exclude_unset，不输出此值。"""
    return None


class MetadataFields(WorkflowModel):
    """默认工厂仅表示未提供；显式 null 仍按非空字段类型拒绝。"""
    name: str = Field(default_factory=_omitted_value)
    code: str = Field(default_factory=_omitted_value)
    description: str = Field(default_factory=_omitted_value)
    symptom: str = Field(default_factory=_omitted_value)
    industry: str = Field(default_factory=_omitted_value)
    device: str = Field(default_factory=_omitted_value)
    versions: list[str] = Field(default_factory=_omitted_value)


class ParameterFields(WorkflowModel):
    key: str
    required: bool = True
    schema_: JsonSchema = Field(alias="schema")


class ParameterPatch(WorkflowModel):
    key: str = Field(default_factory=_omitted_value)
    required: bool = Field(default_factory=_omitted_value)
    schema_: JsonSchema = Field(default_factory=_omitted_value, alias="schema")


class CollectionParameter(ParameterFields):
    id: str | None = Field(default=None, description="复制定义时可保留原字段 ID；新字段省略，由服务器分配。")
    client_ref: str | None = Field(default=None, alias="client_ref", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


class RoleFields(WorkflowModel):
    key: str
    name: str
    description: str = ""
    required: bool = True
    schema_: JsonSchema | None = Field(default=None, alias="schema")


class RolePatch(WorkflowModel):
    key: str = Field(default_factory=_omitted_value)
    name: str = Field(default_factory=_omitted_value)
    description: str = Field(default_factory=_omitted_value)
    required: bool = Field(default_factory=_omitted_value)
    schema_: JsonSchema | None = Field(default=None, alias="schema")


class StepFields(WorkflowModel):
    step_type: Literal["expression", "script"]
    name: str
    description: str = ""
    is_start: bool = False
    parallel_branches: bool = False
    script: ScriptDraft | None = None


class ConclusionFields(WorkflowModel):
    node_type: Literal["conclusion"]
    name: str
    severity: Literal["info", "warning", "error", "critical"] = "info"
    root_cause: str = ""
    repair_recommendation: str = ""


class NodePatch(WorkflowModel):
    name: str = Field(default_factory=_omitted_value)
    description: str = Field(default_factory=_omitted_value)
    is_start: bool = Field(default_factory=_omitted_value)
    parallel_branches: bool = Field(default_factory=_omitted_value)
    step_type: Literal["expression", "script"] = Field(default_factory=_omitted_value)
    script: ScriptDraft | None = None
    severity: Literal["info", "warning", "error", "critical"] = Field(default_factory=_omitted_value)
    root_cause: str = Field(default_factory=_omitted_value)
    repair_recommendation: str = Field(default_factory=_omitted_value)


class CallFields(WorkflowModel):
    key: str
    name: str
    device_role_id: str | None = None
    sample_count: Annotated[int, Field(gt=0)] = 1
    input_bindings: dict[str, Binding] = Field(default_factory=dict)


class ReferencedCallFields(CallFields):
    definition: VersionedRef


class CallPatch(WorkflowModel):
    key: str = Field(default_factory=_omitted_value)
    name: str = Field(default_factory=_omitted_value)
    device_role_id: str | None = None
    sample_count: Annotated[int, Field(gt=0)] = Field(default_factory=_omitted_value)
    input_bindings: dict[str, Binding] = Field(default_factory=_omitted_value)
    definition: VersionedRef = Field(default_factory=_omitted_value)


class TransitionFields(WorkflowModel):
    target: NodeRef
    condition_text: str = ""
    condition_expression: str = ""


class TransitionPatch(WorkflowModel):
    target: NodeRef = Field(default_factory=_omitted_value)
    condition_text: str = Field(default_factory=_omitted_value)
    condition_expression: str = Field(default_factory=_omitted_value)


class DefinitionFields(WorkflowModel):
    key: str
    metadata: CollectionMetadata
    spec: CollectionSpec
    inputs: list[CollectionParameter] = Field(default_factory=list)
    outputs: list[CollectionParameter] = Field(default_factory=list)


class CollectionMetadataPatch(WorkflowModel):
    name: str = Field(default_factory=_omitted_value)
    description: str = Field(default_factory=_omitted_value)
    industry: str = Field(default_factory=_omitted_value)
    device: str = Field(default_factory=_omitted_value)
    versions: list[str] = Field(default_factory=_omitted_value)
    tags: list[str] = Field(default_factory=_omitted_value)


class DefinitionPatch(WorkflowModel):
    key: str = Field(default_factory=_omitted_value)
    metadata: CollectionMetadataPatch = Field(default_factory=_omitted_value)
    spec: CollectionSpec = Field(default_factory=_omitted_value)
    inputs: list[CollectionParameter] = Field(default_factory=_omitted_value)
    outputs: list[CollectionParameter] = Field(default_factory=_omitted_value)
