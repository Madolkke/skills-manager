"""按字段位置投影 Agent 可见表达式环境，不接受客户端声明类型。"""
from typing import Any

from skillhub.models.errors import InvariantError, NotFoundError

from .expression.environment import (
    binding_expression_environment,
    binding_scope_calls,
    conclusion_scope_steps,
    expression_scope_steps,
    project_workflow_expression_environment,
)


def authoring_expression_context(document: dict, selection: dict) -> dict[str, Any]:
    """绑定仅看到前序采集，路径与结论沿用现有拓扑作用域。"""
    workflow = document['workflow']
    nodes = workflow['nodes']
    node = _find(nodes, selection['node_id'], '节点')
    field = selection['field']
    definitions = {(item['id'], item['revision']): item for item in document['collectionSnapshots']}
    inputs = {item['key']: item['schema'] for item in workflow['inputs']}
    roles = workflow['deviceRoles']
    target = None
    if field == 'binding':
        _require_step(node)
        call = _find(node['collectionCalls'], selection.get('call_id'), '采集调用')
        definition = definitions[(call['definition']['id'], call['definition']['revision'])]
        parameter = _find(definition['inputs'], selection.get('input_id'), '采集参数')
        target = parameter['schema']
        visible, _ = binding_scope_calls(nodes, node['id'], call['id'])
        scoped_calls = [entry['call'] for entry in visible.values()] + [call]
        environment = binding_expression_environment(nodes, node['id'], call['id'], definitions, inputs, roles)
    elif field in {'conditionExpression', 'conditionText'}:
        _require_step(node)
        _find(node['topology'], selection.get('transition_id'), '跳转')
        scoped_steps = expression_scope_steps(nodes, node['id'])
        scoped_calls = [call for step in scoped_steps for call in step.get('collectionCalls', [])]
        environment = project_workflow_expression_environment(scoped_steps, definitions, inputs, roles)
        if field == 'conditionExpression':
            target = {'type': 'boolean'}
    elif field in {'rootCause', 'repairRecommendation'}:
        if node.get('nodeType') != 'conclusion':
            raise InvariantError('结论模板必须定位到结论节点。')
        scoped_steps = conclusion_scope_steps(nodes, node['id'])
        scoped_calls = [call for step in scoped_steps for call in step.get('collectionCalls', [])]
        environment = project_workflow_expression_environment(scoped_steps, definitions, inputs, roles)
    else:
        raise InvariantError('不支持的表达式字段。')
    return {'selection': selection, 'environment': environment, 'target_schema': target,
            'collections': [{**call, 'collection': definitions[(call['definition']['id'], call['definition']['revision'])]}
                            for call in scoped_calls],
            'paths': _paths(environment), 'notes': ['[] 表示业务数组元素；采集次数大于 1 时另有最外层采集下标。',
                                               '业务数组长度未知；函数只做静态检查，不执行函数体。']}


def _find(items: list, identity: str | None, label: str) -> dict:
    """拒绝不存在或未提供的定位，避免误给其他字段的作用域。"""
    for item in items:
        if item['id'] == identity:
            return item
    raise NotFoundError(f'{label}不存在：{identity or "未指定"}')


def _require_step(node: dict) -> None:
    """限制采集和路径上下文的节点种类。"""
    if 'stepType' not in node:
        raise InvariantError('采集或路径字段必须定位到步骤。')


def _paths(environment: dict) -> list[dict]:
    """用 [] 模板列出嵌套路径，保留复杂 Schema 而不猜数组长度。"""
    result: list[dict] = []

    def walk(path: str, schema: dict) -> None:
        result.append({'path': path, 'type': schema.get('type', 'any'), 'title': schema.get('title', '')})
        if schema.get('type') == 'object':
            for key, value in schema.get('properties', {}).items():
                walk(f'{path}.{key}', value)
        elif schema.get('type') == 'array':
            walk(path + '[]', schema.get('items', {}))

    for key, schema in environment['inputs'].items():
        walk(f'inputs.{key}', schema)
    for key, output in environment['outputs'].items():
        path = f'outputs.{key}' + ('[0]' if output['sampleCount'] > 1 else '')
        schema = output.get('schema') or {'type': 'object', 'properties': output['fields']}
        walk(path, schema)
    for key, schema in environment['config'].items():
        walk(f'config.{key}', schema)
    for key, schema in environment['topo']['devices'].items():
        walk(f'topo.devices.{key}', schema)
    return result
