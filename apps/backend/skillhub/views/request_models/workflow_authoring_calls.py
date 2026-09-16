"""MCP 采集与绑定操作。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from skillhub.models.rules.workflows.schema import Binding
from skillhub.views.request_models.workflow_authoring_fields import CallFields, CallPatch, DefinitionFields, DefinitionPatch, ReferencedCallFields

ObjectRef = Annotated[str, Field(min_length=1, max_length=200, description="已有对象 ID，或同批先前创建对象的 @client_ref。")]
ClientRef = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$", description="本次请求内唯一引用名，后续使用 @引用名。")]


class AuthoringOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CallAdd(AuthoringOperation):
    """向步骤添加一个精确版本的已有采集定义。"""
    operation: Literal["call.add"]
    node_id: ObjectRef
    client_ref: ClientRef | None = None
    fields: ReferencedCallFields


class CallFromSystem(AuthoringOperation):
    """根据启用的系统命令创建只读来源采集并添加调用。"""
    operation: Literal["call.from_system"]
    node_id: ObjectRef
    client_ref: ClientRef | None = None
    definition_ref: ClientRef | None = None
    command_id: ObjectRef
    fields: CallFields


class CallCreateCollection(AuthoringOperation):
    """创建独立采集定义并添加调用，字段 ID 缺省时自动生成。"""
    operation: Literal["call.create_collection"]
    node_id: ObjectRef
    client_ref: ClientRef | None = None
    definition_ref: ClientRef | None = None
    definition: DefinitionFields
    fields: CallFields


class CallForkCollection(AuthoringOperation):
    """复制当前调用的定义并更新，仅重绑定指定调用，不更改共享定义。"""
    operation: Literal["call.fork_collection"]
    node_id: ObjectRef
    call_id: ObjectRef
    definition_ref: ClientRef | None = None
    fields: DefinitionPatch


class CallUpdate(AuthoringOperation):
    """只修改明确提供的调用字段，inputBindings 显式提供时整体替换。"""
    operation: Literal["call.update"]
    node_id: ObjectRef
    call_id: ObjectRef
    fields: CallPatch


class CallRemove(AuthoringOperation):
    """移除采集调用，其他表达式保持原文并交由校验诊断。"""
    operation: Literal["call.remove"]
    node_id: ObjectRef
    call_id: ObjectRef


class CallReorder(AuthoringOperation):
    """提供该步骤全部调用 ID 的新顺序。"""
    operation: Literal["call.reorder"]
    node_id: ObjectRef
    ids: list[ObjectRef]


class BindingSet(AuthoringOperation):
    """设置指定采集输入的绑定；表达式文本不会被引用替换。"""
    operation: Literal["binding.set"]
    node_id: ObjectRef
    call_id: ObjectRef
    input_id: ObjectRef
    binding: Binding


class BindingRemove(AuthoringOperation):
    """删除指定采集输入的绑定。"""
    operation: Literal["binding.remove"]
    node_id: ObjectRef
    call_id: ObjectRef
    input_id: ObjectRef
