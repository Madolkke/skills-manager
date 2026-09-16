"""不依赖数据库的 MCP 身份、Schema 和事务边界回归。"""

import asyncio
import json
import threading
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

from skillhub.services.mcp_identity import McpAuthenticationRequired, resolve_mcp_actor
from skillhub.views.dependencies import run_mcp_service
from skillhub.views.mcp import WorkflowMCP
from skillhub.views.mcp.results import error_result, success_result
from skillhub.views.mcp.settings import transport_security
from skillhub.views.mcp.tools import create_tools


def test_mock_identity_requires_cookie_without_contacting_configured_endpoint():
    """URL 仅是预留配置；任意非空凭据固定映射模拟用户。"""
    with patch("httpx.get", side_effect=AssertionError("不应调用身份接口")):
        assert resolve_mcp_actor("sso=fake", {"SKILLHUB_MCP_USERINFO_URL": "https://identity.invalid/user"}) == "product-operator"
    for cookie in [None, "", "  "]:
        with pytest.raises(McpAuthenticationRequired):
            resolve_mcp_actor(cookie, {})


def test_tool_schema_is_strict_and_all_nine_tools_have_annotations():
    """参数只在连接层携带身份，编辑操作发布有区分标签的完整 Schema。"""
    async def invoke(*_args):
        return success_result({"summary": "ok"})

    server = WorkflowMCP(create_tools(invoke))
    tools = asyncio.run(server.list_tools())
    assert len(tools) == 9
    for tool in tools:
        assert tool.inputSchema["additionalProperties"] is False
        assert tool.annotations is not None
        assert tool.annotations.openWorldHint is False
        assert not ({"actor", "cookie", "expected_revision"} & tool.inputSchema["properties"].keys())
    apply = next(tool for tool in tools if tool.name == "apply_workflow_changes")
    assert apply.inputSchema["properties"]["changes"]["items"]["discriminator"]["propertyName"] == "operation"
    for arguments in [{"actor": "secret"}, {"limit": "20"}, {"limit": 101}, {"offset": -1}]:
        result = asyncio.run(server.call_authoring_tool("search_workflows", arguments))
        assert result.isError
        assert result.structuredContent["error"]["code"] == "INVALID_ARGUMENT"
        assert "secret" not in result.model_dump_json()
    for arguments in [{"slug": "UpperCase", "description": "test"}, {"slug": "ok", "description": ""},
                      {"slug": "ok", "description": "test", "name": "  "}]:
        result = asyncio.run(server.call_authoring_tool("create_workflow", arguments))
        assert result.isError
        assert result.structuredContent["error"]["code"] == "INVALID_ARGUMENT"


def test_transaction_finishes_before_success_and_commit_errors_escape():
    """事务、Store 和服务都在调用线程内使用，提交失败不会返回结果。"""
    events = []
    caller_thread = threading.get_ident()

    class Factory:
        fail = False

        @contextmanager
        def begin(self):
            assert threading.get_ident() == caller_thread
            events.append("begin")
            yield object()
            events.append("commit")
            if self.fail:
                raise RuntimeError("commit secret")

    class Service:
        def __init__(self, _store, **_kwargs):
            events.append("service")

        def create_workflow(self, **arguments):
            assert arguments["actor"] == "product-operator"
            events.append("operation")
            return {"saved": True}

    factory = Factory()
    with patch("skillhub.views.dependencies.SkillHubStore"), patch("skillhub.views.dependencies.WorkflowAuthoringService", Service):
        assert run_mcp_service(factory, "create_workflow", {}, "sso=secret") == {"saved": True}
        assert events == ["begin", "service", "operation", "commit"]
        factory.fail = True
        with pytest.raises(RuntimeError) as failure:
            run_mcp_service(factory, "create_workflow", {}, "sso=secret")
    result = error_result(failure.value, "create_workflow")
    assert result.isError
    assert result.structuredContent["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in result.model_dump_json()


def test_read_tool_does_not_resolve_cookie():
    """免鉴权读取不会因携带 Cookie 而调用身份解析。"""
    class Factory:
        @contextmanager
        def begin(self):
            yield object()

    class Service:
        def __init__(self, _store, **_kwargs):
            pass

        def search_workflows(self):
            return {"items": []}

    with patch("skillhub.views.dependencies.SkillHubStore"), \
            patch("skillhub.views.dependencies.WorkflowAuthoringService", Service), \
            patch("skillhub.views.dependencies.resolve_mcp_actor", side_effect=AssertionError("读取无需身份")):
        assert run_mcp_service(Factory(), "search_workflows", {}, "unusable-cookie") == {"items": []}


def test_remote_host_and_origin_can_be_added_without_losing_local_defaults():
    """反向代理域名通过环境配置放行，未配置的域名仍保持 SDK 行为。"""
    configured = transport_security({
        "SKILLHUB_MCP_ALLOWED_HOSTS": " skillhub.example.com, skillhub.example.com:* ",
        "SKILLHUB_MCP_ALLOWED_ORIGINS": "https://skillhub.example.com/",
    })
    request = Request({"type": "http", "method": "POST", "path": "/mcp", "headers": [
        (b"host", b"skillhub.example.com"), (b"origin", b"https://skillhub.example.com"), (b"content-type", b"application/json"),
    ]})
    middleware = TransportSecurityMiddleware(configured)
    assert asyncio.run(middleware.validate_request(request, is_post=True)) is None
    local_only = TransportSecurityMiddleware(transport_security({}))
    assert asyncio.run(local_only.validate_request(request, is_post=True)).status_code == 421
    assert "127.0.0.1:*" in configured.allowed_hosts


def test_text_content_keeps_structured_result_for_older_clients():
    """只读取 text 的客户端也能获得完整 ID 和数据，不依赖 structuredContent。"""
    payload = {"skill_id": "skill-example", "summary": "已创建", "validation": {"errors": []}}
    result = success_result(payload)
    assert result.content[0].text == "已创建"
    assert json.loads(result.content[1].text) == result.structuredContent == payload


def test_create_tags_reuse_existing_fields_and_reject_unknown_values():
    """创建工具支持必选标签，并向服务只传递普通字典。"""
    captured = []

    async def invoke(_context, operation, parameters):
        captured.append((operation, parameters))
        return success_result({"summary": "created"})

    tools = create_tools(invoke)
    tool = next(item for item in tools if item.name == "create_workflow")
    arguments = {"slug": "tagged-workflow", "description": "test", "tags": [{"group_id": "domain", "value": "network"}]}
    asyncio.run(tool.run(arguments, context=None))
    assert captured[-1][1]["tags"] == arguments["tags"]
    asyncio.run(tool.run({"slug": "untagged", "description": "test"}, context=None))
    assert captured[-1][1]["tags"] == []
    server = WorkflowMCP(tools)
    for tag in [{"group_id": "domain", "value": "network", "actor": "spoof"}, {"group_id": "domain", "value": 7}]:
        result = asyncio.run(server.call_authoring_tool("create_workflow", {**arguments, "tags": [tag]}))
        assert result.isError
        assert result.structuredContent["error"]["code"] == "INVALID_ARGUMENT"


def test_changes_contract_text_and_structured_schema_match():
    """补充编辑 Schema 后重新构造文本，保证所有客户端读取同一契约。"""
    async def invoke(*_args):
        return success_result({"topic": "changes"})

    tool = next(item for item in create_tools(invoke) if item.name == "get_authoring_contract")
    result = asyncio.run(tool.run({"topic": "changes"}, context=None))
    assert "changesSchema" in result.structuredContent
    assert json.loads(result.content[1].text) == result.structuredContent
