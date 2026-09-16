"""写入口最终校验和回滚：不依赖前端异步诊断。"""
from copy import deepcopy

from skillhub.models.rules.workflows.expression.registry import builtin_function_documents
from tests import test_workflows as workflow_fixtures
from tests.api_command_test_case import ApiCommandTestCase


class BuiltinWriteValidationTest(ApiCommandTestCase):
    _create_workflow = workflow_fixtures.WorkflowApiTest._create_workflow
    _definition = workflow_fixtures.WorkflowApiTest._definition
    _valid_document = workflow_fixtures.WorkflowApiTest._valid_document
    _import_bundle = workflow_fixtures.WorkflowApiTest._import_bundle

    def test_invalid_calls_rejected_without_revision_or_collection_changes(self):
        """条件、模板、绑定均拒绝错误函数，且保存/导入保持数据库原样。"""
        for document in builtin_function_documents():
            self.store.create_expression_function(payload=document, actor='workflow-owner')
        skill = self._create_workflow('builtin-write-test')
        path = f"/api/skills/{skill['skill_id']}/workflow"
        original = self.client.get(path).json()
        headers = {'X-SkillHub-Actor': 'workflow-owner'}
        for field in ['conditionExpression', 'conditionText', 'rootCause']:
            definition = self._definition()
            candidate = self._valid_document(deepcopy(original['document']), definition)
            if field == 'rootCause':
                candidate['workflow']['nodes'][1][field] = '{{ sum(1) }}'
            else:
                candidate['workflow']['nodes'][0]['topology'][0][field] = 'sum(1)' if field == 'conditionExpression' else '{{ sum(1) }}'
            response = self.client.put(path, headers=headers, json={'document': candidate, 'collection_changes': [{'operation': 'create', 'definition': definition}]})
            assert response.status_code == 400, response.text
            assert '函数' in response.text
            assert self.client.get(path).json()['revision'] == original['revision']
            assert self.client.get(f'{path}/collections').json()['definitions'] == []
            bundle = self._import_bundle()
            if field == 'rootCause':
                bundle['workflow']['nodes'][1][field] = '{{ sum(1) }}'
            else:
                bundle['workflow']['nodes'][0]['topology'][0][field] = 'sum(1)' if field == 'conditionExpression' else '{{ sum(1) }}'
            imported = self.client.post(f'{path}/import', headers=headers, json=bundle)
            assert imported.status_code == 400, imported.text
            assert self.client.get(path).json()['revision'] == original['revision']

    def test_single_batch_and_binding_use_the_same_rules(self):
        """同一调用的单条、批量与绑定目标校验使用相同诊断。"""
        for document in builtin_function_documents():
            self.store.create_expression_function(payload=document, actor='workflow-owner')
        single = self.client.post('/api/workflow-expression-validations', json={'source': 'sum(1)'}).json()
        response = self.client.post('/api/workflow-expression-validations/batch', json={'expressions': [
            {'id': 'bad', 'source': 'sum(1)'},
            {'id': 'binding', 'source': '1', 'target_schema': {'type': 'string'}},
        ]})
        assert response.status_code == 200, response.text
        assert response.json()['validations'][0]['diagnostics'] == single['diagnostics']
        assert response.json()['validations'][1]['assignable'] is False
