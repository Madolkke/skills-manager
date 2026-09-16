"""MCP 具体命令的隔离、预检、绑定同步和失败事务。"""
from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.authoring import build_authoring_candidate
from skillhub.models.store import SkillHubStore
from skillhub.services.command_library import CommandLibraryService
from skillhub.views.request_models.workflow_authoring import AuthoringChanges
from tests import test_workflow_authoring_command_details as command_fixtures
from tests import test_workflow_authoring_projection as projection_fixtures
from tests.api_command_test_case import ApiCommandTestCase
from tests.postgres_test_case import PostgresTestCase


class CommandInstanceAuthoringTest(PostgresTestCase):
    call = command_fixtures.WorkflowAuthoringCommandDetailsTest.call

    def setUp(self):
        """建立独立来源和真实事务服务。"""
        super().setUp()
        self.store = SkillHubStore(self.engine)
        self.command = CommandLibraryService(self.store).create_system(payload={
            "key": "instance_source", "name": "路由", "expression": "show routes <vrf>",
            "outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        }, actor="admin-console")

    def test_instance_edit_and_read_only_preflight(self):
        """预检 SQL 全只读，实例互相隔离，编辑与解绑遵守来源所有权。"""
        from sqlalchemy import event

        skill = self.call("create_workflow", slug="mcp-instances", description="测试", actor="product-operator")["skill_id"]
        changes = [
            {"operation": "node.add", "client_ref": "step", "fields": {"stepType": "expression", "name": "检查", "isStart": True}},
            {"operation": "call.from_system", "node_id": "@step", "client_ref": "fixed", "command_id": self.command["id"],
             "command_template": "show another command", "fields": {"key": "fixed", "name": "固定"}},
            {"operation": "call.from_system", "node_id": "@step", "client_ref": "dynamic", "command_id": self.command["id"],
             "command_template": "show routes <tenant> <tenant>", "fields": {"key": "dynamic", "name": "动态",
                "inputBindings": {"input_tenant": {"kind": "literal", "value": "default"}}}},
        ]
        statements = []

        def record(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement.lstrip().split()[0].upper())

        event.listen(self.engine, "before_cursor_execute", record)
        try:
            preview = self.call("validate_workflow_changes", skill_id=skill, changes=changes, validation_policy="strict")
        finally:
            event.remove(self.engine, "before_cursor_execute", record)
        assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements)
        assert preview["can_save"] and len(preview["collectionSnapshots"]) == 2
        assert {item["code"] for item in preview["validation"]["warnings"]} >= {"COMMAND_MATCH_DYNAMIC", "COMMAND_SOURCE_MISMATCH"}
        saved = self.call("apply_workflow_changes", skill_id=skill, changes=changes, validation_policy="strict", actor="product-operator")
        document = self.call("get_workflow", skill_id=skill, view="full")["document"]
        original = deepcopy(document)
        step = saved["id_mappings"]["step"]
        call = saved["id_mappings"]["dynamic"]
        updated = self.call("apply_workflow_changes", skill_id=skill, actor="product-operator", validation_policy="strict", changes=[
            {"operation": "call.set_command", "node_id": step, "call_id": call, "command_template": "show routes <tenant> detail"}])
        result = self.call("get_workflow", skill_id=skill, view="full")
        definition = next(item for item in result["document"]["collectionSnapshots"] if item["inputs"])
        assert definition["sourceBindingMode"] == "concrete-command"
        assert definition["sourceSystemCommandId"] == self.command["id"]
        assert definition["forkedFrom"]["id"] in {item["id"] for item in original["collectionSnapshots"]}
        assert result["document"]["workflow"]["nodes"][0]["collectionCalls"][1]["inputBindings"]["input_tenant"]["value"] == "default"
        self.call("apply_workflow_changes", skill_id=skill, actor="product-operator", validation_policy="strict", changes=[
            {"operation": "call.set_command", "node_id": step, "call_id": call, "command_template": "show routes default"}])
        result = self.call("get_workflow", skill_id=skill, view="full")
        assert not result["document"]["workflow"]["nodes"][0]["collectionCalls"][1]["inputBindings"]
        assert all(not item["inputs"] for item in result["document"]["collectionSnapshots"])
        before = self.call("search_collections")["total"]
        revision = result["revision"]
        with pytest.raises(InvariantError):
            self.call("apply_workflow_changes", skill_id=skill, actor="product-operator", changes=[
                {"operation": "call.set_command", "node_id": step, "call_id": call, "command_template": "show changed"},
                {"operation": "call.set_command", "node_id": step, "call_id": call, "command_template": "show <unfinished"}])
        assert self.call("search_collections")["total"] == before
        assert self.call("get_workflow", skill_id=skill)["revision"] == revision
        self.call("apply_workflow_changes", skill_id=skill, actor="product-operator", changes=[
            {"operation": "call.fork_collection", "node_id": step, "call_id": call, "fields": {"metadata": {"name": "独立"}}}])
        final = self.call("get_workflow", skill_id=skill, view="full")["document"]
        independent = next(item for item in final["collectionSnapshots"] if item["metadata"]["name"] == "独立")
        assert not independent.get("sourceSystemCommandId") and not independent.get("sourceBindingMode")
        assert updated["saved"]


def test_from_system_requires_concrete_command():
    """严格工具协议不能默认为来源表达式。"""
    with pytest.raises(ValidationError, match="command_template"):
        TypeAdapter(AuthoringChanges).validate_python([{"operation": "call.from_system", "node_id": "node", "command_id": "source",
                                                     "fields": {"key": "routes", "name": "路由"}}])


class LegacyInstanceConversionTest(ApiCommandTestCase):
    _source = projection_fixtures.WorkflowAuthoringProjectionTest._source
    _candidate = projection_fixtures.WorkflowAuthoringProjectionTest._candidate
    _create_workflow = projection_fixtures.WorkflowAuthoringProjectionTest._create_workflow
    _definition = projection_fixtures.WorkflowAuthoringProjectionTest._definition
    _valid_document = projection_fixtures.WorkflowAuthoringProjectionTest._valid_document

    def test_legacy_conversion_retains_source_and_parameter_ids(self):
        """旧数据不自动改写，显式转换只影响指定调用。"""
        source = self._source()
        definition = self.store.authoring_system_command(source["id"], "legacy")
        skill, document, changes = self._candidate(definition=definition)
        saved = self.store.save_workflow(skill_id=skill, document=document, collection_changes=changes, actor="workflow-owner")
        node = saved["document"]["workflow"]["nodes"][0]
        call = node["collectionCalls"][0]
        candidate = build_authoring_candidate(saved["document"], [{"operation": "call.set_command", "node_id": node["id"],
            "call_id": call["id"], "command_template": "show interfaces <interface>"}],
            resolve_system_command=self.store.authoring_system_command, resolve_collection=lambda *_: definition)
        converted = candidate["document"]["collectionSnapshots"][0]
        assert converted["sourceBindingMode"] == "concrete-command"
        assert converted["sourceSystemCommandId"] == source["id"]
        assert converted["inputs"][0]["key"] == "interface"
        assert "sourceBindingMode" not in saved["document"]["collectionSnapshots"][0]
