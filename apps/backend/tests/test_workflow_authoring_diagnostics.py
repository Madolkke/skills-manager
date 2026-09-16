"""MCP 完整字段诊断保留既有错误等级和 UTF-16 范围。"""

import json
from copy import deepcopy
from pathlib import Path

from skillhub.models.rules.workflows import validate_workflow_document
from skillhub.models.rules.workflows.authoring_diagnostics import supplement_expression_diagnostics
from skillhub.models.rules.workflows.expression import FUNCTIONS
from skillhub.models.rules.workflows.expression.checker_ast import utf16_length
from skillhub.models.rules.workflows.save_policy import blocking_workflow_errors
from tests import test_workflow_authoring_rules as fixtures


def fixture():
    """复用完整复杂采集示例，其中包含数组和前序输入绑定。"""
    path = Path(__file__).resolve().parents[2] / 'frontend/src/features/workflow/fixtures/complex-schema-workflow.json'
    return json.loads(path.read_text(encoding='utf-8'))


def validate(document):
    """先保留原文档规则，再补全部表达式诊断。"""
    issues = validate_workflow_document(document, FUNCTIONS)
    base = {'errors': [item for item in issues if item['severity'] == 'error'],
            'warnings': [item for item in issues if item['severity'] == 'warning']}
    return base, supplement_expression_diagnostics(document, base, FUNCTIONS)


def test_unknown_property_and_syntax_are_reported_as_checker_warnings():
    document = fixture()
    step = document['workflow']['nodes'][0]
    transition = step['topology'][0]
    for source, expected in [('outputs.routes.routes[0].absent', 'UNKNOWN_PROPERTY'), ('outputs.routes[', 'PYTHON_SYNTAX')]:
        transition['conditionExpression'] = source
        base, result = validate(document)
        assert not any(item['code'] == expected and item['selection'].get('field') == 'conditionExpression'
                       for item in base['warnings'] + base['errors'])
        diagnostic = next(item for item in result['warnings'] if item['code'] == expected)
        assert diagnostic['selection'] == {'type': 'step', 'id': step['id'], 'section': 'paths', 'itemId': transition['id'], 'field': 'conditionExpression'}
        assert 0 <= diagnostic['start'] < diagnostic['end'] <= utf16_length(source) + 1


def test_function_diagnostics_are_not_duplicated_and_have_positions():
    document = fixture()
    document['workflow']['nodes'][0]['topology'][0]['conditionExpression'] = 'sum(1) + sum(2)'
    base, result = validate(document)
    expected = [item for item in base['errors'] if item['code'].startswith('FUNCTION_')]
    actual = [item for item in result['errors'] if item['code'].startswith('FUNCTION_')]
    assert len(actual) == len(expected) == 2
    assert actual[0]['start'] != actual[1]['start']
    assert all(item['start'] < item['end'] for item in actual)


def test_templates_keep_chinese_and_non_bmp_offsets():
    document = fixture()
    source = '诊断😀：{{ outputs.routes.routes[0].absent }}'
    document['workflow']['nodes'][0]['topology'][0]['conditionText'] = source
    conclusion = next(item for item in document['workflow']['nodes'] if item.get('nodeType') == 'conclusion')
    conclusion['rootCause'] = source
    original = deepcopy(document)
    _, result = validate(document)
    diagnostics = [item for item in result['warnings'] if item['code'] == 'UNKNOWN_PROPERTY']
    assert {item['selection']['field'] for item in diagnostics} == {'conditionText', 'rootCause'}
    expected_start = utf16_length(source[:source.index('outputs.')])
    expected_end = utf16_length(source[:source.index('absent') + len('absent')])
    assert all((item['start'], item['end']) == (expected_start, expected_end) for item in diagnostics)
    assert document == original


def test_binding_uses_preceding_scope_and_enriches_existing_severity():
    document = fixture()
    step = document['workflow']['nodes'][0]
    call = step['collectionCalls'][2]
    definition = next(item for item in document['collectionSnapshots'] if item['id'] == call['definition']['id'])
    input_id = definition['inputs'][0]['id']
    call['inputBindings'][input_id] = {'kind': 'expression', 'expression': 'outputs.fabric[0].matrix[0][0].value', 'reference': {}}
    base, result = validate(document)
    baseline = next(item for item in base['errors'] if item['code'] == 'UNKNOWN_PROPERTY')
    diagnostic = next(item for item in result['errors'] if item['code'] == 'UNKNOWN_PROPERTY')
    assert diagnostic['selection'] == baseline['selection']
    assert diagnostic['selection']['field'] == f'binding.{input_id}'
    assert diagnostic['start'] < diagnostic['end']
    call['inputBindings'][input_id]['expression'] = '1'
    _, result = validate(document)
    mismatch = next(item for item in result['errors'] if item['code'] == 'INCOMPATIBLE_BINDING_SCHEMA')
    assert (mismatch['start'], mismatch['end']) == (0, 1)


def test_fork_removed_input_keeps_binding_and_reports_broken_reference():
    initial = fixtures.apply([fixtures.step(), {'operation': 'call.add', 'node_id': '@step', 'client_ref': 'call', 'fields': {
        'key': 'a', 'name': '接口', 'definition': {'id': 'c1', 'revision': 3},
        'inputBindings': {'ci': {'kind': 'expression', 'expression': "'保持原文'"}},
    }}])
    mapping = initial['id_mappings']
    result = fixtures.apply([{'operation': 'call.fork_collection', 'node_id': mapping['step'], 'call_id': mapping['call'],
                             'fields': {'inputs': []}}], initial['document'])
    document = result['document']
    document['workflow']['metadata']['description'] = '删除输入诊断'
    base, complete = validate(document)
    assert not any(item['code'] == 'BROKEN_REFERENCE' for item in base['errors'])
    diagnostic = next(item for item in complete['errors'] if item['code'] == 'BROKEN_REFERENCE')
    assert diagnostic['selection'] == {'type': 'step', 'id': mapping['step'], 'section': 'collections', 'itemId': mapping['call'], 'field': 'binding.ci'}
    assert document['workflow']['nodes'][0]['collectionCalls'][0]['inputBindings']['ci']['expression'] == "'保持原文'"
    assert not blocking_workflow_errors(complete, validation_policy='draft')
    assert diagnostic in blocking_workflow_errors(complete, validation_policy='strict')
