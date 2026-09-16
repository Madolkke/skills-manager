"""Agent 可直接使用系统命令详情构造采集绑定，无需读取源码猜测参数 ID。"""

from sqlalchemy import event

from skillhub.models.store import SkillHubStore
from skillhub.services.command_library import CommandLibraryService
from skillhub.services.workflow_authoring import WorkflowAuthoringService
from tests.postgres_test_case import PostgresTestCase


class WorkflowAuthoringCommandDetailsTest(PostgresTestCase):
    """详情投影与正式命令转 Collection 保持一致，并避免 N+1 查询。"""

    def setUp(self):
        """建立包含可选、重复及必填捕获的命令和嵌套输出。"""
        super().setUp()
        self.store = SkillHubStore(self.engine)
        self.output_schema = {"type": "object", "required": ["routes"], "additionalProperties": False, "properties": {
            "routes": {"type": "array", "title": "路由", "items": {"type": "object", "required": ["vrf"],
                "additionalProperties": False, "properties": {"vrf": {"type": "string", "title": "实例"},
                    "hops": {"type": "array", "title": "下一跳", "items": {"type": "string", "title": "地址"}}}}}}}
        self.command = CommandLibraryService(self.store).create_system(payload={
            "key": "mcp_parameter_details", "name": "参数详情", "description": "真实参数 Schema",
            "expression": "show routes <vrf> [ <interface> ] <peer>&<1-3>", "metadata": {"name": "参数详情"},
            "outputSchema": self.output_schema, "samples": [], "enabled": True,
        }, actor="admin-console")

    def call(self, method, **kwargs):
        """用真实 Service 和事务边界执行。"""
        with self.store.transaction() as store:
            return getattr(WorkflowAuthoringService(store), method)(**kwargs)

    def test_details_supply_stable_binding_parameters_without_extra_queries(self):
        """搜索完成态的 captures 值不会误作声明；详情和正式采集参数逐字段一致。"""
        statements = []

        def record(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", record)
        try:
            compact = self.call("search_system_commands", details=False)
            compact_count = len(statements)
            statements.clear()
            details = self.call("search_system_commands", details=True)
            assert len(statements) == compact_count == 1
        finally:
            event.remove(self.engine, "before_cursor_execute", record)
        assert "inputs" not in compact["items"][0]
        command = details["items"][0]
        assert command["outputSchema"] == self.output_schema
        inputs = {item["key"]: item for item in command["inputs"]}
        assert inputs["vrf"]["id"] == "input_vrf"
        assert inputs["vrf"]["required"] is True
        assert inputs["interface"]["required"] is False
        assert inputs["peer"]["schema"]["type"] == "array"
        assert inputs["peer"]["schema"]["items"]["type"] == "string"
        exact = self.call("search_system_commands", query="show routes default ethernet0 peer1 peer2", details=True)["items"][0]
        assert exact["captures"]
        assert exact["inputs"] == command["inputs"]

        created = self.call("create_workflow", slug="mcp-details", description="按详情创建", actor="product-operator")
        bindings = {item["id"]: {"kind": "literal", "value": ["peer1"] if item["schema"]["type"] == "array" else "default"}
                    for item in command["inputs"]}
        self.call("apply_workflow_changes", skill_id=created["skill_id"], actor="product-operator", changes=[
            {"operation": "node.add", "client_ref": "start", "fields": {"stepType": "expression", "name": "检查", "isStart": True}},
            {"operation": "call.from_system", "node_id": "@start", "command_id": command["id"],
             "fields": {"key": "routes", "name": "路由", "inputBindings": bindings}},
        ])
        document = self.call("get_workflow", skill_id=created["skill_id"], view="full")["document"]
        assert document["collectionSnapshots"][0]["inputs"] == command["inputs"]
        saved_bindings = document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]
        assert saved_bindings.keys() == bindings.keys()
        for input_id, binding in bindings.items():
            assert saved_bindings[input_id]["kind"] == binding["kind"]
            assert saved_bindings[input_id]["value"] == binding["value"]
