"""MCP 创作入口复用现有标签目录和必选约束。"""

import pytest
from sqlalchemy import func, select

from skillhub.models.errors import InvariantError
from skillhub.models.schema import orm
from skillhub.models.store import SkillHubStore
from skillhub.services.workflow_authoring import WorkflowAuthoringService
from tests.postgres_test_case import PostgresTestCase


class WorkflowAuthoringTagsTest(PostgresTestCase):
    """从真实必选标签目录创建工作流，不通过自动补标签绕过约束。"""

    def setUp(self):
        """先添加枚举值，再设置标签组为必选。"""
        super().setUp()
        self.store = SkillHubStore(self.engine)
        group = {"group_id": "mcp-required", "display_name": "必选领域", "description": "MCP 创建回归", "sort_order": 0,
                 "actor": "product-operator"}
        self.store.create_tag_group(**group)
        self.store.create_tag_value(group_id="mcp-required", value="network", display_name="网络", description="网络工作流", sort_order=0,
                                    actor="product-operator")
        self.store.update_tag_group(**group, required=True)

    def call(self, method, **kwargs):
        """与 MCP 一样将完整 Service 调用放在外层事务中。"""
        with self.store.transaction() as store:
            return getattr(WorkflowAuthoringService(store), method)(**kwargs)

    def counts(self):
        """失败不能留下业务文档、初始版本、标签、创建事实或审计。"""
        entities = (orm.Skill, orm.SkillVersion, orm.Workflow, orm.SkillTag, orm.SkillCreationFact, orm.AuditEvent)
        with self.engine.connect() as connection:
            return {entity.__name__: connection.scalar(select(func.count()).select_from(entity)) for entity in entities}

    def test_contract_exposes_required_tags_and_creation_is_atomic(self):
        """Agent 可先发现必选项；缺失失败无残留，显式合法标签后创建成功。"""
        contract = self.call("get_authoring_contract", topic="overview")
        group = next(item for item in contract["tag_groups"] if item["id"] == "mcp-required")
        assert group["required"] is True
        assert group["free_form"] is False
        assert group["values"][0]["value"] == "network"
        assert group["values"][0]["display_name"] == "网络"
        before = self.counts()
        for tags in ([], [{"group_id": "mcp-required", "value": "missing"}]):
            with pytest.raises(InvariantError):
                self.call("create_workflow", slug="mcp-required-demo", description="必选标签回归", tags=tags, actor="product-operator")
            assert self.counts() == before
        created = self.call("create_workflow", slug="mcp-required-demo", description="必选标签回归",
                            tags=[{"group_id": "mcp-required", "value": "network"}], actor="product-operator")
        assert created["saved"] is True
        after = self.counts()
        for entity in (orm.Skill, orm.SkillVersion, orm.Workflow, orm.SkillTag, orm.SkillCreationFact):
            assert after[entity.__name__] == before[entity.__name__] + 1
        with self.engine.connect() as connection:
            assert connection.scalar(select(orm.Skill.owner_ref).where(orm.Skill.id == created["skill_id"])) == "product-operator"
            assert connection.scalar(select(orm.SkillTag.tag_value).where(orm.SkillTag.skill_id == created["skill_id"])) == "network"
