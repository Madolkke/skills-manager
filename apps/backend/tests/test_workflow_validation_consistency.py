from __future__ import annotations

from copy import deepcopy

from skillhub.models.rules.workflows import normalize_workflow_document, validate_workflow_document
from tests import test_workflow_rules


def _document() -> dict:
    return normalize_workflow_document(test_workflow_rules.WorkflowRulesTest()._document())


def test_required_literal_values_distinguish_empty_from_falsey() -> None:
    cases = [
        ({"kind": "literal", "reference": {}, "value": None}, "string", True),
        ({"kind": "literal", "reference": {}}, "string", True),
        ({"kind": "literal", "reference": {}, "value": ""}, "string", True),
        ({"kind": "literal", "reference": {}, "value": 0}, "integer", False),
        ({"kind": "literal", "reference": {}, "value": False}, "boolean", False),
    ]
    for binding, schema_type, missing in cases:
        document = _document()
        parameter = document["collectionSnapshots"][0]["inputs"][0]
        parameter["schema"] = {"type": schema_type, "title": "参数", "description": ""}
        document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"][parameter["id"]] = binding

        codes = {item["code"] for item in validate_workflow_document(document)}

        assert ("MISSING_REQUIRED_BINDING" in codes) is missing


def test_missing_identity_codes_are_distinct_from_duplicate_codes() -> None:
    document = _document()
    workflow = document["workflow"]
    step = workflow["nodes"][0]
    definition = document["collectionSnapshots"][0]
    workflow["inputs"][0].update(id="", key="")
    workflow["deviceRoles"] = [{"id": "", "key": "", "name": "设备", "description": "", "required": True}]
    step["id"] = ""
    step["collectionCalls"][0]["id"] = ""
    step["topology"][0]["id"] = ""
    definition["inputs"][0].update(id="", key="")
    definition["outputs"] = [{"id": "", "key": "", "required": True, "schema": {"type": "string", "title": "输出", "description": ""}}]
    definition["spec"]["outputSamples"][0]["id"] = ""

    issues = validate_workflow_document(document)
    codes = {item["code"] for item in issues}
    expected = {
        "MISSING_NODE_ID", "MISSING_INPUT_ID", "MISSING_INPUT_KEY", "MISSING_ROLE_ID", "MISSING_ROLE_KEY", "MISSING_CALL_ID",
        "MISSING_TRANSITION_ID", "MISSING_COLLECTION_INPUT_ID", "MISSING_COLLECTION_INPUT_KEY", "MISSING_COLLECTION_OUTPUT_ID",
        "MISSING_COLLECTION_OUTPUT_KEY", "MISSING_COLLECTION_SAMPLE_ID",
    }

    assert expected <= codes
    assert len(issues) == len({item["id"] for item in issues})
    assert not ({code.replace("MISSING_", "DUPLICATE_", 1) for code in expected} & codes)


def test_non_empty_duplicates_keep_duplicate_codes() -> None:
    document = _document()
    workflow = document["workflow"]
    step = workflow["nodes"][0]
    definition = document["collectionSnapshots"][0]
    workflow["nodes"].append(deepcopy(workflow["nodes"][1]))
    workflow["inputs"].append(deepcopy(workflow["inputs"][0]))
    role = {"id": "role-1", "key": "device", "name": "设备", "description": "", "required": True}
    workflow["deviceRoles"] = [role, deepcopy(role)]
    step["collectionCalls"].append(deepcopy(step["collectionCalls"][0]))
    step["topology"].append(deepcopy(step["topology"][0]))
    definition["inputs"].append(deepcopy(definition["inputs"][0]))
    output = {"id": "output-1", "key": "status", "required": True, "schema": {"type": "string", "title": "输出", "description": ""}}
    definition["outputs"] = [output, deepcopy(output)]
    definition["spec"]["outputSamples"].append(deepcopy(definition["spec"]["outputSamples"][0]))
    document["collectionSnapshots"].append(deepcopy(definition))

    codes = {item["code"] for item in validate_workflow_document(document)}

    assert {
        "DUPLICATE_NODE_ID", "DUPLICATE_INPUT_ID", "DUPLICATE_INPUT_KEY", "DUPLICATE_ROLE_ID", "DUPLICATE_ROLE_KEY",
        "DUPLICATE_CALL_ID", "DUPLICATE_CALL_KEY", "DUPLICATE_TRANSITION_ID", "DUPLICATE_COLLECTION_REFERENCE",
        "DUPLICATE_COLLECTION_INPUT_ID", "DUPLICATE_COLLECTION_INPUT_KEY", "DUPLICATE_COLLECTION_OUTPUT_ID",
        "DUPLICATE_COLLECTION_OUTPUT_KEY", "DUPLICATE_COLLECTION_SAMPLE_ID",
    } <= codes


def test_issue_ids_are_stable_and_use_precise_call_selection() -> None:
    document = _document()
    step = document["workflow"]["nodes"][0]
    step["id"] = "step-start"
    parameter = document["collectionSnapshots"][0]["inputs"][0]
    parameter["id"] = "parameter-required"
    call = step["collectionCalls"][0]
    call["id"] = "call-interface"
    call["inputBindings"] = {"parameter-required": {"kind": "literal", "reference": {}, "value": None}}

    first = validate_workflow_document(document)
    issue = next(item for item in first if item["code"] == "MISSING_REQUIRED_BINDING")
    assert first == validate_workflow_document(document)
    document["workflow"]["metadata"]["name"] = ""
    unchanged = next(item for item in validate_workflow_document(document) if item["code"] == "MISSING_REQUIRED_BINDING")

    assert issue["id"] == unchanged["id"]
    assert issue["id"] == "workflow-issue/missing_required_binding/step/step-start//collections/call-interface/binding.parameter-required/0"
    assert issue["selection"] == {
        "type": "step", "id": "step-start", "section": "collections", "itemId": "call-interface", "field": "binding.parameter-required"
    }
