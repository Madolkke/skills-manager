"""按操作区分的 MCP 作者编辑输入契约。"""

from typing import Annotated, Literal

from pydantic import Field

from skillhub.views.request_models.workflow_authoring_calls import (
    AuthoringOperation,
    BindingRemove,
    BindingSet,
    CallAdd,
    CallCreateCollection,
    CallForkCollection,
    CallFromSystem,
    CallRemove,
    CallReorder,
    CallSetCommand,
    CallUpdate,
    ClientRef,
    ObjectRef,
)
from skillhub.views.request_models.workflow_authoring_fields import (
    ConclusionFields,
    MetadataFields,
    NodePatch,
    ParameterFields,
    ParameterPatch,
    RoleFields,
    RolePatch,
    StepFields,
    TransitionFields,
    TransitionPatch,
)


class MetadataUpdate(AuthoringOperation):
    """更新工作流元信息，未提供的字段保持原值。"""
    operation: Literal["metadata.update"]
    fields: MetadataFields


class InputAdd(AuthoringOperation):
    """添加全局输入，ID 自动生成。"""
    operation: Literal["input.add"]
    client_ref: ClientRef | None = None
    fields: ParameterFields


class InputUpdate(AuthoringOperation):
    """局部更新全局输入，Schema 显式提供时整体替换。"""
    operation: Literal["input.update"]
    input_id: ObjectRef
    fields: ParameterPatch


class InputRemove(AuthoringOperation):
    """删除全局输入，保留其他位置的原始引用供诊断。"""
    operation: Literal["input.remove"]
    input_id: ObjectRef


class InputReorder(AuthoringOperation):
    """提供全部全局输入 ID 的新顺序。"""
    operation: Literal["input.reorder"]
    ids: list[ObjectRef]


class RoleAdd(AuthoringOperation):
    """添加设备角色。"""
    operation: Literal["role.add"]
    client_ref: ClientRef | None = None
    fields: RoleFields


class RoleUpdate(AuthoringOperation):
    """局部更新设备角色。"""
    operation: Literal["role.update"]
    role_id: ObjectRef
    fields: RolePatch


class RoleRemove(AuthoringOperation):
    """删除设备角色，保留采集调用中的引用供诊断。"""
    operation: Literal["role.remove"]
    role_id: ObjectRef


class RoleReorder(AuthoringOperation):
    """提供全部设备角色 ID 的新顺序。"""
    operation: Literal["role.reorder"]
    ids: list[ObjectRef]


class NodeAdd(AuthoringOperation):
    """添加步骤或结论；采集调用和拓扑使用对应操作添加。"""
    operation: Literal["node.add"]
    client_ref: ClientRef | None = None
    fields: StepFields | ConclusionFields


class NodeUpdate(AuthoringOperation):
    """局部更新节点，支持脚本、非互斥标记及结论模板。"""
    operation: Literal["node.update"]
    node_id: ObjectRef
    fields: NodePatch


class NodeRemove(AuthoringOperation):
    """删除节点及指向该节点的全部拓扑边。"""
    operation: Literal["node.remove"]
    node_id: ObjectRef


class NodeReorder(AuthoringOperation):
    """提供全部步骤和结论 ID 的新顺序。"""
    operation: Literal["node.reorder"]
    ids: list[ObjectRef]


class TransitionAdd(AuthoringOperation):
    """添加步骤跳转；target.id 可引用同批已创建的节点。"""
    operation: Literal["transition.add"]
    node_id: ObjectRef
    client_ref: ClientRef | None = None
    fields: TransitionFields


class TransitionUpdate(AuthoringOperation):
    """更新跳转目标、条件表达式或条件说明模板。"""
    operation: Literal["transition.update"]
    node_id: ObjectRef
    transition_id: ObjectRef
    fields: TransitionPatch


class TransitionRemove(AuthoringOperation):
    """删除指定跳转。"""
    operation: Literal["transition.remove"]
    node_id: ObjectRef
    transition_id: ObjectRef


class TransitionReorder(AuthoringOperation):
    """提供该步骤全部跳转 ID 的新顺序。"""
    operation: Literal["transition.reorder"]
    node_id: ObjectRef
    ids: list[ObjectRef]


AuthoringChange = Annotated[
    MetadataUpdate | InputAdd | InputUpdate | InputRemove | InputReorder
    | RoleAdd | RoleUpdate | RoleRemove | RoleReorder | NodeAdd | NodeUpdate | NodeRemove | NodeReorder
    | TransitionAdd | TransitionUpdate | TransitionRemove | TransitionReorder
    | CallSetCommand | CallAdd | CallFromSystem | CallCreateCollection | CallForkCollection | CallUpdate | CallRemove | CallReorder
    | BindingSet | BindingRemove,
    Field(discriminator="operation"),
]
AuthoringChanges = Annotated[list[AuthoringChange], Field(max_length=500, description="按顺序应用的局部操作，整批原子保存。")]


class AuthoringChangesPayload(AuthoringOperation):
    changes: AuthoringChanges = Field(default_factory=list)
