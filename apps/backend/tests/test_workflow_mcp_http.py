"""官方 MCP 客户端通过真实 HTTP 验证协议、身份和写入闭环。"""

import asyncio
import logging
import os
import socket
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select

from skillhub.bootstrap.app import create_app
from skillhub.models.errors import PermissionDeniedError
from skillhub.models.schema import orm
from tests.postgres_test_case import PostgresTestCase


class WorkflowMcpHttpTest(PostgresTestCase):
    """每个测试独立 PostgreSQL，监听系统分配端口并运行完整 lifespan。"""

    def setUp(self):
        super().setUp()
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}/mcp"
        self.app = create_app(self.engine)
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            if not self.thread.is_alive():
                break
            time.sleep(0.02)
        assert self.server.started, "MCP 测试服务未完成启动"

    def tearDown(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.socket.close()
        assert not self.thread.is_alive(), "MCP 服务未关闭"
        super().tearDown()

    def test_sdk_discovery_identity_and_edit_cycle(self):
        """匿名查询、模拟身份写入、草稿预检与严格失败都经过真实协议。"""
        asyncio.run(self._edit_cycle())

    def test_commit_failure_is_error_without_cookie_or_partial_rows(self):
        """真实写入在提交前失败时，HTTP 返回错误且连接凭据不进入日志或落库。"""
        cookie = "sso=mcp-cookie-transport-unique"
        captured = []

        class Capture(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        handler = Capture()
        logging.getLogger().addHandler(handler)
        try:
            asyncio.run(self._commit_failure(cookie))
        finally:
            logging.getLogger().removeHandler(handler)
        assert cookie not in "\n".join(captured)
        assert "mcp-cookie-transport-unique" not in "\n".join(captured)
        with self.engine.connect() as connection:
            for entity in (orm.Skill, orm.Workflow, orm.AuditEvent):
                rows = connection.execute(orm.select_entity(entity)).mappings().all()
                assert "mcp-cookie-transport-unique" not in repr(rows)
            assert connection.scalar(select(orm.Skill.id).where(orm.Skill.slug == "mcp-commit-fails")) is None

    async def _commit_failure(self, cookie):
        """注入实际事务退出前失败，验证异常经过回滚后才映射 MCP 结果。"""
        factory = self.app.state.session_factory

        class CommitFailure:
            @contextmanager
            def begin(self):
                with factory.begin() as session:
                    yield session
                    raise RuntimeError("模拟提交阶段异常，不应返回成功")

        async with httpx.AsyncClient(headers={"Cookie": cookie}) as http:
            async with streamable_http_client(self.url, http_client=http) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                with patch.object(self.app.state, "session_factory", CommitFailure()):
                    failed = await session.call_tool("create_workflow", {"slug": "mcp-commit-fails", "description": "回滚测试"})
                assert failed.isError
                assert failed.structuredContent["error"]["code"] == "INTERNAL_ERROR"
                assert "mcp-cookie-transport-unique" not in failed.model_dump_json()
                assert (await session.call_tool("search_workflows", {"query": "mcp-commit-fails"})).structuredContent["total"] == 0

    async def _edit_cycle(self):
        """保持会话内工具调用顺序，写入成功后用独立匿名连接读取。"""
        async with streamable_http_client(self.url) as (read, write, session_id), ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "SkillHub Workflow"
            assert session_id() is None
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "search_workflows", "get_workflow", "get_authoring_contract", "search_system_commands", "search_collections",
                "get_expression_context", "validate_workflow_changes", "create_workflow", "apply_workflow_changes",
            }
            contract = await session.call_tool("get_authoring_contract", {"topic": "changes"})
            assert not contract.isError
            assert "changesSchema" in contract.structuredContent
            assert not (await session.call_tool("search_system_commands")).isError
            denied = await session.call_tool("create_workflow", {"slug": "mcp-cookie-missing", "description": "test"})
            assert denied.structuredContent["error"]["code"] == "AUTH_REQUIRED"
            invalid = await session.call_tool("search_workflows", {"actor": "product-operator"})
            assert invalid.structuredContent["error"]["code"] == "INVALID_ARGUMENT"
            assert (await session.call_tool("search_workflows")).structuredContent["total"] == 0

        with patch.dict(os.environ, {"SKILLHUB_MCP_USERINFO_URL": "http://identity.invalid/profile"}), \
                patch("httpx.get", side_effect=AssertionError("模拟身份不发出 HTTP")):
            async with httpx.AsyncClient(headers={"Cookie": "sso=mcp-test", "X-SkillHub-Actor": "spoofed-user"}) as http:
                async with streamable_http_client(self.url, http_client=http) as (read, write, _), ClientSession(read, write) as session:
                    await session.initialize()
                    created = await session.call_tool("create_workflow", {"slug": "mcp-http-demo", "description": "协议验收"})
                    assert not created.isError, created
                    skill_id = created.structuredContent["skill_id"]
                    changes = [{"operation": "metadata.update", "fields": {"description": "通过 MCP 修改"}}]
                    strict = await session.call_tool("apply_workflow_changes", {
                        "skill_id": skill_id, "changes": changes, "validation_policy": "strict",
                    })
                    assert strict.isError
                    assert strict.structuredContent["error"]["validation"]["errors"]
                    unchanged = await session.call_tool("get_workflow", {"skill_id": skill_id, "view": "full"})
                    assert unchanged.structuredContent["document"]["workflow"]["metadata"]["description"] == "协议验收"
                    saved = await session.call_tool("apply_workflow_changes", {"skill_id": skill_id, "changes": changes})
                    assert not saved.isError, saved
                    assert saved.structuredContent["saved"] is True
                    assert saved.structuredContent["validation"]["errors"]
                    with patch("skillhub.services.workflow_authoring.WorkflowAuthoringService.apply_workflow_changes",
                               side_effect=PermissionDeniedError("无编辑权限")):
                        refused = await session.call_tool("apply_workflow_changes", {"skill_id": skill_id, "changes": []})
                    assert refused.structuredContent["error"]["code"] == "PERMISSION_DENIED"

        async with streamable_http_client(self.url) as (read, write, _), ClientSession(read, write) as session:
            await session.initialize()
            final = await session.call_tool("get_workflow", {"skill_id": skill_id, "view": "full"})
            assert final.structuredContent["document"]["workflow"]["metadata"]["description"] == "通过 MCP 修改"
            assert "capabilities" not in final.structuredContent
            preview = await session.call_tool("validate_workflow_changes", {"skill_id": skill_id, "changes": []})
            assert not preview.isError
            assert preview.structuredContent["saved"] is False
            assert preview.structuredContent["can_save"] is True
            assert "mcp-test" not in final.model_dump_json()
