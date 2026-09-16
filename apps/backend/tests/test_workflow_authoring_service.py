"""MCP 创作服务与 PostgreSQL 事务的行为验收。"""
from copy import deepcopy

import pytest
from sqlalchemy import func, select

from skillhub.models.errors import InvariantError, PermissionDeniedError
from skillhub.models.rules.workflows.expression.registry import builtin_function_documents
from skillhub.models.schema import orm
from skillhub.models.store import SkillHubStore
from skillhub.services.command_library import CommandLibraryService
from skillhub.services.workflow_authoring import WorkflowAuthoringService
from tests.postgres_test_case import PostgresTestCase


class WorkflowAuthoringServiceTest(PostgresTestCase):
    def setUp(self):
        """独立测试库；每次调用使用与 MCP 一致的外层事务。"""
        super().setUp()
        self.store = SkillHubStore(self.engine)
        for item in builtin_function_documents():
            self.store.create_expression_function(payload=item, actor='product-operator')
        self.skill = self.call('create_workflow', slug='mcp-service-test', description='创作服务测试', actor='product-operator')['skill_id']

    def call(self, method, **kwargs):
        """服务成功后提交，异常离开上下文回滚。"""
        with self.store.transaction() as store:
            return getattr(WorkflowAuthoringService(store), method)(**kwargs)

    def counts(self):
        """预检及失败操作不得改变这些持久化事实。"""
        with self.engine.connect() as connection:
            return tuple(connection.scalar(select(func.count()).select_from(entity)) for entity in
                         (orm.WorkflowCollectionDefinition, orm.WorkflowCollectionRevision, orm.AuditEvent, orm.SkillVisitEvent))

    def test_preview_draft_strict_and_transaction_rollback(self):
        """草稿可继续编辑，严格模式拒绝未完成状态，错误批次没有部分写入。"""
        before = self.counts()
        changes = [{'operation': 'node.add', 'client_ref': 'start', 'fields': {'stepType': 'expression', 'name': '检查', 'isStart': True}}]
        preview = self.call('validate_workflow_changes', skill_id=self.skill, changes=changes)
        assert not preview['saved']
        assert self.counts() == before
        created = self.call('apply_workflow_changes', skill_id=self.skill, changes=changes, actor='product-operator')
        step = created['id_mappings']['start']
        with pytest.raises(InvariantError):
            self.call('apply_workflow_changes', skill_id=self.skill, changes=[{'operation': 'node.update', 'node_id': step, 'fields': {'isStart': False}}],
                      validation_policy='strict', actor='product-operator')
        assert self.call('get_workflow', skill_id=self.skill, view='full')['document']['workflow']['nodes'][0]['isStart']
        before = self.counts()
        with pytest.raises(InvariantError):
            self.call('apply_workflow_changes', skill_id=self.skill, changes=[
                {'operation': 'call.create_collection', 'node_id': step, 'fields': {'key': 'custom', 'name': '自定义'},
                 'definition': {'key': 'mcp_custom', 'metadata': {'name': '自定义'}, 'spec': {'collectionType': 'cli', 'commandTemplate': 'show status'}}},
                {'operation': 'node.add', 'client_ref': 'end', 'fields': {'nodeType': 'conclusion', 'name': '结束'}},
                {'operation': 'transition.add', 'node_id': step, 'fields': {'target': {'id': '@end'}, 'conditionExpression': 'sum(1)'}}],
                actor='product-operator')
        assert self.counts() == before

    def test_sources_fork_and_anonymous_read(self):
        """系统采集输入/输出保持完整，fork 不更新共享来源，读取不计访问。"""
        metadata = {'name': '嵌套输出', 'description': '对象数组'}
        schema = {'type': 'object', 'required': ['rows'], 'additionalProperties': False, 'properties': {'rows': {
            'type': 'array', 'title': '记录', 'items': {'type': 'object', 'properties': {'vrf': {'type': 'string', 'title': '实例'}},
                                                  'required': ['vrf'], 'additionalProperties': False}}}}
        command = CommandLibraryService(self.store).create_system(payload={
            'key': 'mcp_nested', 'name': metadata['name'], 'expression': 'show routes <vrf>', 'metadata': metadata,
            'description': '对象数组', 'outputSchema': schema, 'samples': [], 'enabled': True}, actor='admin-console')
        result = self.call('apply_workflow_changes', skill_id=self.skill, changes=[
            {'operation': 'node.add', 'client_ref': 'step', 'fields': {'stepType': 'expression', 'name': '检查', 'isStart': True}},
            {'operation': 'call.from_system', 'node_id': '@step', 'client_ref': 'call', 'command_id': command['id'], 'command_template': 'show routes <vrf>',
             'fields': {'key': 'routes', 'name': '路由', 'inputBindings': {'input_vrf': {'kind': 'literal', 'value': 'default'}}}},
        ], actor='product-operator')
        detail = self.call('get_workflow', skill_id=self.skill, view='full')
        assert 'capabilities' not in detail
        definition = detail['document']['collectionSnapshots'][0]
        original = deepcopy(definition)
        assert definition['sourceSystemCommandId'] == command['id']
        assert definition['outputs'][0]['schema']['items']['properties']['vrf']['type'] == 'string'
        self.call('apply_workflow_changes', skill_id=self.skill, changes=[{
            'operation': 'call.fork_collection', 'node_id': result['id_mappings']['step'], 'call_id': result['id_mappings']['call'],
            'fields': {'metadata': {'name': '独立副本', 'description': '仅此调用'}}}], actor='product-operator')
        forked = self.call('get_workflow', skill_id=self.skill, view='full')['document']['collectionSnapshots'][0]
        assert forked['id'] != original['id']
        assert not forked.get('sourceSystemCommandId')
        assert forked['forkedFrom'] == {'id': original['id'], 'revision': original['revision']}
        stored = self.call('search_collections', definition_id=original['id'], revision=original['revision'], details=True)['items'][0]
        assert stored == original
        before = self.counts()
        self.call('search_workflows', query='创作')
        self.call('get_workflow', skill_id=self.skill)
        assert self.counts() == before

    def test_permission_and_search_system_only(self):
        """已有 Workflow 的编辑权限仍由 Store 权限检查决定。"""
        with pytest.raises(PermissionDeniedError):
            self.call('apply_workflow_changes', skill_id=self.skill, changes=[], actor='unauthorized')
        result = self.call('search_system_commands', query='')
        assert all(item['source'] == 'system' for item in result['items'])

    def test_full_expression_diagnostics_match_preview_save_and_read(self):
        """MCP 三个入口返回同一警告与位置，严格保存不将 checker 提醒升级。"""
        changes = [
            {'operation': 'node.add', 'client_ref': 'step', 'fields': {'stepType': 'expression', 'name': '检查', 'isStart': True}},
            {'operation': 'node.add', 'client_ref': 'end', 'fields': {'nodeType': 'conclusion', 'name': '结束'}},
            {'operation': 'transition.add', 'node_id': '@step', 'fields': {
                'target': {'id': '@end'}, 'conditionExpression': 'outputs.absent'}},
        ]
        before = self.counts()
        preview = self.call('validate_workflow_changes', skill_id=self.skill, changes=changes, validation_policy='strict')
        assert self.counts() == before
        assert preview['can_save']
        warning = next(item for item in preview['validation']['warnings'] if item['code'] == 'UNKNOWN_PROPERTY')
        assert warning['start'] == 0 and warning['end'] == len('outputs.absent')
        saved = self.call('apply_workflow_changes', skill_id=self.skill, changes=changes, validation_policy='strict', actor='product-operator')
        loaded = self.call('get_workflow', skill_id=self.skill, view='full')
        assert loaded['validation'] == saved['validation']
        assert any(item['code'] == 'UNKNOWN_PROPERTY' and 'start' in item for item in saved['validation']['warnings'])
        rest = self.store.workflow_detail(skill_id=self.skill, actor='product-operator')
        assert not any(item['code'] == 'UNKNOWN_PROPERTY' for item in rest['validation']['warnings'])
