from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.source_diagnostics import validate_source_diagnostics


def _document():
    """源输出由后序步骤和结论共享。"""
    return {
        "collectionSnapshots": [
            {"id": "source", "revision": 1, "outputs": [{"id": "status", "key": "status", "schema": {"type": "string"}}]},
            {"id": "consumer", "revision": 1, "inputs": [{"id": "input", "key": "input", "schema": {"type": "string"}}]},
        ],
        "workflow": {"inputs": [], "nodes": [
            {"id": "first", "stepType": "expression", "collectionCalls": [
                {"id": "source", "key": "", "definition": {"id": "source", "revision": 1}},
            ], "topology": [{"id": "next", "target": {"id": "second"}}]},
            {"id": "second", "stepType": "expression", "collectionCalls": [
                {"id": "consumer", "definition": {"id": "consumer", "revision": 1}, "inputBindings": {}},
            ], "topology": [{"id": "done", "target": {"id": "done"}}]},
            {"id": "done", "nodeType": "conclusion"},
        ]},
    }


@pytest.mark.parametrize("field", ["conditionExpression", "conditionText", "binding", "rootCause", "repairRecommendation", "script"])
@pytest.mark.parametrize("change", ["remove", "type"])
def test_source_removal_rejects_every_downstream_reference(field, change):
    document = _document()
    step = document["workflow"]["nodes"][1]
    if field == "conditionExpression":
        step["topology"][0][field] = "outputs.status != ''"
    elif field == "conditionText":
        step["topology"][0][field] = "state={{ outputs.status }}"
    elif field == "binding":
        step["collectionCalls"][0]["inputBindings"]["input"] = {"kind": "expression", "expression": "outputs.status"}
    elif field == "script":
        step["script"] = {"source": "print(outputs.status)"}
    else:
        document["workflow"]["nodes"][2][field] = "state={{ outputs.status }}"
    candidate = deepcopy(document)
    if change == "remove":
        candidate["collectionSnapshots"][0]["outputs"] = []
    else:
        candidate["collectionSnapshots"][0]["outputs"][0]["schema"]["type"] = "integer"
    with pytest.raises(InvariantError, match="表达式引用"):
        validate_source_diagnostics(document, candidate)


def test_source_diagnostics_preserves_unrelated_draft_errors():
    document = _document()
    document["workflow"]["nodes"][1]["topology"][0]["conditionExpression"] = "outputs.unknown != ''"
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][0]["metadata"] = {"name": "重命名"}
    validate_source_diagnostics(document, candidate)


def test_source_diagnostics_rejects_candidate_output_conflicts():
    document = _document()
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][1]["outputs"] = [{"id": "another", "key": "status", "schema": {"type": "string"}}]
    with pytest.raises(InvariantError, match="作用域"):
        validate_source_diagnostics(document, candidate)


def test_source_diagnostics_rejects_nested_script_type_change():
    document = _document()
    document["collectionSnapshots"][0]["outputs"][0]["schema"] = {
        "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False,
    }
    document["workflow"]["nodes"][1]["script"] = {"source": "print(outputs.status.value)"}
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][0]["outputs"][0]["schema"]["properties"]["value"]["type"] = "integer"
    with pytest.raises(InvariantError, match="类型"):
        validate_source_diagnostics(document, candidate)


def test_unconnected_reference_and_plain_template_text_do_not_block():
    document = _document()
    document["workflow"]["nodes"][0]["topology"] = []
    document["workflow"]["nodes"][1]["topology"][0]["conditionExpression"] = "outputs.status == ''"
    document["workflow"]["nodes"][0]["description"] = "outputs.status 是文档示例"
    document["workflow"]["nodes"][2]["rootCause"] = "示例 outputs.status"
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][0]["outputs"][0]["schema"]["type"] = "integer"
    validate_source_diagnostics(document, candidate)


def test_source_diagnostics_rejects_removed_bracket_property():
    document = _document()
    document["collectionSnapshots"][0]["outputs"][0]["schema"] = {
        "type": "object", "properties": {"value": {"type": "string"}}, "required": [], "additionalProperties": False,
    }
    document["workflow"]["nodes"][1]["topology"][0]["conditionExpression"] = "outputs.status['value'] == ''"
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][0]["outputs"][0]["schema"]["properties"] = {}
    with pytest.raises(InvariantError, match="路径失效"):
        validate_source_diagnostics(document, candidate)


def test_source_diagnostics_checks_output_bindings_individually():
    document = _document()
    call = document["workflow"]["nodes"][1]["collectionCalls"][0]
    call["inputBindings"] = {
        "existing-draft-error": {"kind": "literal", "value": ""},
        "input": {"kind": "collection_output", "reference": {"call_id": "source", "output_id": "status"}},
    }
    candidate = deepcopy(document)
    candidate["collectionSnapshots"][0]["outputs"] = []
    with pytest.raises(InvariantError, match="绑定的输出不存在"):
        validate_source_diagnostics(document, candidate)
