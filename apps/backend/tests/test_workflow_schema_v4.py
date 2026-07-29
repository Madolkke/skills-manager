from __future__ import annotations

from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, migrate_workflow_document, normalize_collection_definition
from skillhub.models.rules.workflows.expression import evaluate_expression, expression_contract, validate_expression
from skillhub.models.rules.workflows.json_schema import schemas_assignable, value_matches_schema
from skillhub.services.workflows import WorkflowService


def test_nested_object_array_schema_is_normalized_and_sorted() -> None:
    definition = normalize_collection_definition(
        {
            "id": "collection-table",
            "revision": 1,
            "key": "table",
            "metadata": {"name": "表格", "description": "", "industry": "", "device": "", "versions": [], "tags": []},
            "spec": {"collectionType": "cli", "commandTemplate": "show table", "outputSamples": []},
            "inputs": [],
            "outputs": [
                {
                    "id": "output-rows",
                    "key": "rows",
                    "required": True,
                    "schema": {
                        "type": "array",
                        "title": "行",
                        "description": "",
                        "items": {
                            "type": "object",
                            "title": "行记录",
                            "description": "",
                            "properties": {
                                "status": {"type": "string", "title": "状态", "description": ""},
                                "name": {"type": "string", "title": "名称", "description": ""},
                            },
                            "required": ["status", "name"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
        }
    )

    item_schema = definition["outputs"][0]["schema"]["items"]
    assert list(item_schema["properties"]) == ["name", "status"]
    assert item_schema["required"] == ["name", "status"]


def test_v3_document_migrates_metadata_and_loose_structures() -> None:
    document = {
        "documentType": "workflow_bundle",
        "workflow": {
            "id": "workflow-1",
            "revision": 3,
            "metadata": {"name": "迁移", "description": "说明"},
            "inputs": [{"id": "input-rows", "key": "rows", "name": "数据行", "description": "旧数组", "dataType": "array", "required": True}],
            "deviceRoles": [],
            "nodes": [],
        },
        "collectionSnapshots": [],
    }

    migrated = migrate_workflow_document(3, document)

    assert DOCUMENT_SCHEMA_VERSION == 4
    field = migrated["workflow"]["inputs"][0]
    assert set(field) == {"id", "key", "required", "schema"}
    assert field["schema"]["title"] == "数据行"
    assert field["schema"]["items"]["x-skillhub-legacy-loose"] is True


def test_structural_assignability_and_literal_validation() -> None:
    integer = {"type": "integer"}
    number = {"type": "number"}
    target = {"type": "object", "properties": {"count": number}, "required": ["count"], "additionalProperties": False}
    source = {"type": "object", "properties": {"count": integer, "extra": {"type": "string"}}, "required": ["count"], "additionalProperties": False}

    assert schemas_assignable(integer, number)
    assert not schemas_assignable(number, integer)
    assert schemas_assignable(source, target)
    assert value_matches_schema({"count": 2}, target)
    assert not value_matches_schema({"count": "2"}, target)


def test_expression_contract_typecheck_and_trusted_evaluator() -> None:
    environment = {
        "inputs": {"region": {"type": "string"}},
        "outputs": {"inventory": {"rows": {"type": "array", "items": {"type": "integer"}}}},
    }
    result = validate_expression("inputs.region.lower() == 'cn' and sum(outputs.inventory.rows) > 0", environment)

    assert result["inferredType"]["kind"] == "boolean"
    assert result["diagnostics"] == []
    assert expression_contract()["roots"] == ["inputs", "outputs"]
    assert expression_contract()["contractVersion"] == 2
    assert evaluate_expression("inputs.region.lower()", inputs={"region": "CN"}, outputs={}) == "cn"


def test_expression_validates_fixed_multi_sample_indexes() -> None:
    environment = {
        "inputs": {"offset": {"type": "integer"}, "label": {"type": "string"}},
        "outputs": {
            "status": {
                "sampleCount": 3,
                "fields": {"version": {"type": "string"}},
            },
            "single": {
                "sampleCount": 1,
                "fields": {"version": {"type": "string"}},
            },
        },
    }

    for source in (
        "outputs.status[0].version",
        "outputs.status[-3].version",
        "outputs.status[inputs.offset].version",
        "outputs.status[1:]",
        "outputs.single.version",
    ):
        assert validate_expression(source, environment)["diagnostics"] == []

    expected = {
        "outputs.status.version": "SAMPLE_INDEX_REQUIRED",
        "outputs.single[0].version": "SAMPLE_INDEX_NOT_ALLOWED",
        "outputs.single[:].version": "SAMPLE_INDEX_NOT_ALLOWED",
        "outputs.status[3].version": "SAMPLE_INDEX_OUT_OF_RANGE",
        "outputs.status[-4].version": "SAMPLE_INDEX_OUT_OF_RANGE",
        "outputs.status[inputs.label].version": "INVALID_SAMPLE_INDEX_TYPE",
    }
    for source, code in expected.items():
        assert [item["code"] for item in validate_expression(source, environment)["diagnostics"]] == [code]


def test_expression_reports_forbidden_and_positioned_diagnostics() -> None:
    result = validate_expression("lambda value: value", {"inputs": {}, "outputs": {}})

    assert result["diagnostics"][0]["code"] == "FORBIDDEN_LAMBDA"
    assert result["diagnostics"][0]["end"] > result["diagnostics"][0]["start"]


def test_expression_batch_preserves_request_order() -> None:
    service = WorkflowService(object())  # type: ignore[arg-type]

    result = service.validate_expressions(
        expressions=[
            {"id": "second", "source": "outputs.status[0].version"},
            {"id": "first", "source": "outputs.status.version"},
        ],
        environment={
            "inputs": {},
            "outputs": {
                "status": {
                    "sampleCount": 2,
                    "fields": {"version": {"type": "string"}},
                }
            },
        },
    )

    assert [item["id"] for item in result["validations"]] == ["second", "first"]
    assert result["validations"][0]["diagnostics"] == []
    assert result["validations"][1]["diagnostics"][0]["code"] == "SAMPLE_INDEX_REQUIRED"
