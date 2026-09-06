from copy import deepcopy

import pytest

from skillhub.models.rules.workflows.source_compatibility import _validate_source_compatibility


@pytest.mark.parametrize("expression,source_schema,target_schema", [
    ("inputs.data", {"type": "object", "properties": {"label": {"type": "string"}}, "required": [], "additionalProperties": False},
     {"type": "object", "properties": {"label": {"type": "string"}}, "required": [], "additionalProperties": False}),
    ("inputs.data.split(',')", {"type": "string"}, {"type": "array", "items": {"type": "string"}}),
    ("inputs.data or 'fallback'", {"type": "string"}, {"type": "string"}),
])
def test_source_expression_binding_keeps_internal_types(expression, source_schema, target_schema):
    """同步入口保留可选字段及函数推导信息，不能依赖公开序列化回读。"""
    call = {"id": "call", "key": "", "definition": {"id": "source", "revision": 1},
            "inputBindings": {"input": {"kind": "expression", "expression": expression}}}
    desired = {"id": "source", "revision": 1, "outputs": [],
               "inputs": [{"id": "input", "key": "input", "required": True, "schema": target_schema}]}
    document = {"collectionSnapshots": [desired], "workflow": {
        "inputs": [{"id": "data", "key": "data", "schema": source_schema}],
        "nodes": [{"id": "step", "stepType": "expression", "collectionCalls": [call], "topology": []}],
    }}
    _validate_source_compatibility(document=document, source_call=call, current=deepcopy(desired), desired=desired)
