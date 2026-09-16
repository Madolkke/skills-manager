"""Workflow MCP 工具声明，只负责请求类型和服务调用适配。"""

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import TypeAdapter

from skillhub.views.mcp.results import success_result
from skillhub.views.request_models.common import SkillSlug
from skillhub.views.request_models.mcp import (
    AuthoringSkillTag,
    ContractTopic,
    CreateDescription,
    ExpressionSelection,
    Identifier,
    Limit,
    Offset,
    Revision,
    ValidationPolicy,
    WorkflowName,
    WorkflowView,
)
from skillhub.views.request_models.workflow_authoring import AuthoringChange, AuthoringChanges

Invoker = Callable[[Context, str, dict[str, Any]], Awaitable[CallToolResult]]


def create_tools(invoke: Invoker) -> list[Tool]:
    """创建强类型工具目录；读工具不触发身份解析。"""

    async def search_workflows(
        ctx: Context, query: str = "", include_archived: bool = False, offset: Offset = 0, limit: Limit = 20,
    ) -> CallToolResult:
        """按名称、slug、说明搜索工作流，默认排除归档项，返回摘要和网页入口。"""
        return await invoke(ctx, "search_workflows", {
            "query": query, "include_archived": include_archived, "offset": offset, "limit": limit,
        })

    async def get_workflow(
        ctx: Context, skill_id: Identifier, view: WorkflowView = "outline", node_id: Identifier | None = None,
    ) -> CallToolResult:
        """读取工作流大纲、完整文档或指定节点，以及相关采集快照、校验和同步状态。"""
        return await invoke(ctx, "get_workflow", {"skill_id": skill_id, "view": view, "node_id": node_id})

    async def get_authoring_contract(ctx: Context, topic: ContractTopic = "overview") -> CallToolResult:
        """按主题获取作者模型、局部编辑操作、采集、表达式或日志 SQL 契约；不提供函数体。"""
        result = await invoke(ctx, "get_authoring_contract", {"topic": topic})
        if topic == "changes" and not result.isError and result.structuredContent is not None:
            result.structuredContent["changesSchema"] = TypeAdapter(AuthoringChanges).json_schema(by_alias=True)
            return success_result(result.structuredContent)
        return result

    async def search_system_commands(
        ctx: Context, query: str = "", target_version: str | None = None, details: bool = False, offset: Offset = 0, limit: Limit = 20,
    ) -> CallToolResult:
        """搜索已启用的系统命令，支持命令、Key、名称及设备版本；详情包含完整嵌套 Schema；ruleInputs 仅是规则捕获，实例输入来自 command_template。"""
        return await invoke(ctx, "search_system_commands", {
            "query": query, "target_version": target_version, "details": details, "offset": offset, "limit": limit,
        })

    async def search_collections(
        ctx: Context, query: str = "", definition_id: Identifier | None = None, revision: Revision | None = None,
        details: bool = False, offset: Offset = 0, limit: Limit = 20,
    ) -> CallToolResult:
        """搜索共享采集定义或读取指定精确版本，返回类型和来源，不查询用户命令库。"""
        return await invoke(ctx, "search_collections", {
            "query": query, "definition_id": definition_id, "revision": revision,
            "details": details, "offset": offset, "limit": limit,
        })

    async def get_expression_context(
        ctx: Context, skill_id: Identifier, selection: ExpressionSelection, changes: AuthoringChanges | None = None,
    ) -> CallToolResult:
        """根据字段位置返回可见输入、前序采集输出、Schema、采集次数和目标类型，可包含尚未保存的改动。"""
        return await invoke(ctx, "get_expression_context", {
            "skill_id": skill_id, "selection": selection.model_dump(exclude_none=True), "changes": _changes(changes),
        })

    async def validate_workflow_changes(
        ctx: Context, skill_id: Identifier, changes: AuthoringChanges | None = None, validation_policy: ValidationPolicy = "draft",
    ) -> CallToolResult:
        """无写入地构造并校验候选工作流，返回修改摘要、字段诊断和预计 ID 映射。"""
        return await invoke(ctx, "validate_workflow_changes", {
            "skill_id": skill_id, "changes": _changes(changes), "validation_policy": validation_policy,
        })

    async def create_workflow(
        ctx: Context, slug: SkillSlug, description: CreateDescription, name: WorkflowName | None = None, tags: list[AuthoringSkillTag] = [],
    ) -> CallToolResult:
        """创建 Skill 和空白工作流；连接须携带非空 Cookie，owner 固定为当前模拟用户。超时后请先查询状态。"""
        return await invoke(ctx, "create_workflow", {
            "slug": slug, "description": description, "name": name, "tags": [tag.model_dump() for tag in tags],
        })

    async def apply_workflow_changes(
        ctx: Context, skill_id: Identifier, changes: AuthoringChanges, validation_policy: ValidationPolicy = "draft",
    ) -> CallToolResult:
        """原子应用局部编辑，连接须携带非空 Cookie；draft 沿用网页草稿规则，strict 要求无错误。超时后先读取状态。"""
        return await invoke(ctx, "apply_workflow_changes", {
            "skill_id": skill_id, "changes": _changes(changes), "validation_policy": validation_policy,
        })

    functions: list[Callable[..., Awaitable[CallToolResult]]] = [
        search_workflows, get_workflow, get_authoring_contract, search_system_commands, search_collections,
        get_expression_context, validate_workflow_changes, create_workflow, apply_workflow_changes,
    ]
    tools = []
    for function in functions:
        writing = function.__name__ in {"create_workflow", "apply_workflow_changes"}
        tool = Tool.from_function(function, annotations=ToolAnnotations(
            readOnlyHint=not writing, destructiveHint=function.__name__ == "apply_workflow_changes",
            idempotentHint=not writing, openWorldHint=False,
        ))
        tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
        tool.fn_metadata.arg_model.model_config["strict"] = True
        tool.fn_metadata.arg_model.model_rebuild(force=True)
        tool.parameters = tool.fn_metadata.arg_model.model_json_schema()
        tools.append(tool)
    return tools


def _changes(changes: list[AuthoringChange] | None) -> list[dict[str, Any]]:
    """保留局部更新未提供字段与显式空值的区别。"""
    return [change.model_dump(mode="json", by_alias=True, exclude_unset=True) for change in changes or []]
