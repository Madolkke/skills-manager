"""在现有 API 进程中提供无状态 Streamable HTTP MCP。"""

from os import environ
from typing import Any

from fastapi import FastAPI
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult
from starlette.concurrency import run_in_threadpool

from skillhub.views.dependencies import run_mcp_service
from skillhub.views.mcp.results import error_result, success_result
from skillhub.views.mcp.settings import transport_security
from skillhub.views.mcp.tools import create_tools


class WorkflowMCP(FastMCP):
    """使用 SDK 传输协议，并对参数错误保持结构化、安全的响应。"""

    def __init__(self, tools: list[Tool]):
        """保存强类型目录，供 SDK 分发前进行严格校验。"""
        self.authoring_tools = {tool.name: tool for tool in tools}
        super().__init__(
            "SkillHub Workflow", tools=tools, stateless_http=True, json_response=True,
            streamable_http_path="/mcp",
            transport_security=transport_security(environ),
            instructions="先查询作者契约和可复用资产，再校验并保存。读取无需身份；写入需连接 Cookie，本期固定模拟 product-operator。",
        )
        self._mcp_server.call_tool(validate_input=False)(self.call_authoring_tool)

    async def call_authoring_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """拒绝未知参数；错误不回显输入值或凭据。"""
        try:
            tool = self.authoring_tools.get(name)
            if tool is None:
                return CallToolResult(
                    content=[], structuredContent={"error": {"code": "UNKNOWN_TOOL", "message": "工具不存在。"}}, isError=True,
                )
            tool.fn_metadata.arg_model.model_validate(arguments, strict=True)
            result = await super().call_tool(name, arguments)
            assert isinstance(result, CallToolResult)
            return result
        except Exception as error:
            return error_result(error, name)


def register_mcp(app: FastAPI) -> WorkflowMCP:
    """复用父应用事务工厂，最后挂载子路由以保留精确 /mcp 地址。"""

    async def invoke(ctx: Context, operation: str, parameters: dict[str, Any]) -> CallToolResult:
        """只从当前请求读取 Cookie，线程池返回时事务已完成提交或回滚。"""
        try:
            cookie = None
            if operation in {"create_workflow", "apply_workflow_changes"}:
                request = ctx.request_context.request
                cookie = request.headers.get("cookie") if request is not None else None
            payload = await run_in_threadpool(run_mcp_service, app.state.session_factory, operation, parameters, cookie)
            return success_result(payload)
        except Exception as error:
            return error_result(error, operation)

    server = WorkflowMCP(create_tools(invoke))
    app.mount("/", server.streamable_http_app())
    app.state.mcp_server = server
    return server
