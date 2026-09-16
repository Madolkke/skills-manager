"""真实复杂 Schema 的字段作用域投影。"""
import json
from pathlib import Path

import pytest

from skillhub.models.errors import NotFoundError
from skillhub.models.rules.workflows.authoring_context import authoring_expression_context


@pytest.fixture
def document():
    """复用前端完整演示快照，避免仅测试简化数组目录。"""
    path = Path(__file__).resolve().parents[2] / 'frontend/src/features/workflow/fixtures/complex-schema-workflow.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_binding_context_has_preceding_calls_and_target(document):
    """BGP 参数只得到接口与路由输出，不得到后续 Fabric。"""
    step = document['workflow']['nodes'][0]
    call = step['collectionCalls'][2]
    definition = next(item for item in document['collectionSnapshots'] if item['id'] == call['definition']['id'])
    result = authoring_expression_context(document, {'node_id': step['id'], 'field': 'binding', 'call_id': call['id'], 'input_id': definition['inputs'][0]['id']})
    assert set(result['environment']['outputs']) == {'interfaces', 'routes'}
    assert result['target_schema']['type'] == 'string'
    assert 'outputs.routes.routes[].next_hops[].address' in {item['path'] for item in result['paths']}


def test_condition_context_keeps_sample_and_business_array_layers(document):
    """多次采集最外层 [0] 与业务数组 [] 各自保留。"""
    step = document['workflow']['nodes'][0]
    result = authoring_expression_context(document, {'node_id': step['id'], 'field': 'conditionExpression', 'transition_id': step['topology'][0]['id']})
    assert result['environment']['outputs']['fabric']['sampleCount'] == 3
    assert 'outputs.fabric[0].matrix[][].healthy' in {item['path'] for item in result['paths']}
    assert result['target_schema'] == {'type': 'boolean'}


def test_missing_selection_rejected(document):
    """非法位置不回退到全工作流作用域。"""
    with pytest.raises(NotFoundError):
        authoring_expression_context(document, {'node_id': 'absent', 'field': 'rootCause'})
