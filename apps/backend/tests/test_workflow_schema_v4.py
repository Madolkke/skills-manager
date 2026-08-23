from __future__ import annotations

import pytest

from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, migrate_workflow_document, normalize_collection_definition
from skillhub.models.rules.workflows.expression import evaluate_expression, expression_contract, validate_expression
from skillhub.models.rules.workflows.expression.environment import workflow_expression_environment
from skillhub.models.rules.workflows.json_schema import schemas_assignable, value_matches_schema
from skillhub.models.rules.workflows.validation import _step_expression_environment
from skillhub.services.workflows import WorkflowService
from skillhub.views.request_models.workflows import WorkflowExpressionBatchValidationPayload, WorkflowExpressionEnvironmentPayload


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

    assert DOCUMENT_SCHEMA_VERSION == 5
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
    assert expression_contract()["roots"] == ["inputs", "outputs", "config", "topo"]
    assert evaluate_expression("inputs.region.lower()", inputs={"region": "CN"}, outputs={}) == "cn"


def test_expression_validates_fixed_multi_sample_indexes_and_keeps_config_root() -> None:
    environment = {
        "inputs": {"offset": {"type": "integer"}, "label": {"type": "string"}},
        "outputs": {
            "status": {"sampleCount": 3, "fields": {"version": {"type": "string"}}},
            "single": {"sampleCount": 1, "fields": {"version": {"type": "string"}}},
        },
        "config": {"interface": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    }

    for source in (
        "outputs.status[0].version",
        "outputs.status[-3].version",
        "outputs.status[inputs.offset].version",
        "outputs.status[1:]",
        "outputs.single.version",
        "config.interface.name",
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

    sliced = validate_expression("outputs.status[1:].version", environment)
    assert [item["code"] for item in sliced["diagnostics"]] == ["SAMPLE_INDEX_REQUIRED"]
    assert sliced["inferredType"] == {"kind": "string"}


def test_expression_batch_preserves_order_and_rejects_duplicate_ids() -> None:
    service = WorkflowService(object())  # type: ignore[arg-type]
    environment = {"inputs": {}, "outputs": {"status": {"sampleCount": 2, "fields": {"version": {"type": "string"}}}}, "config": {}}
    result = service.validate_expressions(
        expressions=[
            {"id": "second", "source": "outputs.status[0].version"},
            {"id": "first", "source": "outputs.status.version"},
        ],
        environment=environment,
    )

    assert [item["id"] for item in result["validations"]] == ["second", "first"]
    assert result["validations"][0]["diagnostics"] == []
    assert result["validations"][1]["diagnostics"][0]["code"] == "SAMPLE_INDEX_REQUIRED"

    with pytest.raises(ValueError, match="IDs must be unique"):
        WorkflowExpressionBatchValidationPayload.model_validate({
            "expressions": [{"id": "same", "source": "True"}, {"id": "same", "source": "False"}],
            "environment": environment,
        })


def test_invalid_duplicate_call_keys_use_first_definition_for_environment_projection() -> None:
    document = {
        "workflow": {
            "inputs": [],
            "nodes": [{"id": "step", "collectionCalls": [
                {"id": "first", "key": "status", "sampleCount": 1, "definition": {"id": "one", "revision": 1}},
                {"id": "second", "key": "status", "sampleCount": 3, "definition": {"id": "two", "revision": 1}},
            ]}],
        },
        "collectionSnapshots": [
            {"id": "one", "revision": 1, "spec": {"collectionType": "cli"}, "outputs": [{"key": "version", "schema": {"type": "string"}}]},
            {"id": "two", "revision": 1, "spec": {"collectionType": "cli"}, "outputs": [{"key": "count", "schema": {"type": "integer"}}]},
        ],
    }
    environment = _step_expression_environment(document["workflow"]["nodes"][0], {("one", 1): document["collectionSnapshots"][0], ("two", 1): document["collectionSnapshots"][1]}, {})

    assert environment["outputs"]["status"]["sampleCount"] == 1
    assert set(environment["outputs"]["status"]["fields"]) == {"version"}


def test_unscoped_output_schema_is_projected_as_direct_expression_value() -> None:
    environment = {
        "inputs": {},
        "outputs": {
            "state": {"sampleCount": 1, "fields": {}, "schema": {"type": "string"}},
            "details": {
                "sampleCount": 1,
                "fields": {},
                "schema": {
                    "type": "object",
                    "title": "详情",
                    "description": "",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                    "additionalProperties": False,
                },
            },
            "samples": {"sampleCount": 2, "fields": {}, "schema": {"type": "string"}},
        },
    }

    assert validate_expression("outputs.state == 'up'", environment)["diagnostics"] == []
    assert validate_expression("outputs.details.status == 'up'", environment)["diagnostics"] == []
    assert validate_expression("outputs.samples[0] == 'up'", environment)["diagnostics"] == []
    assert validate_expression("outputs.samples", environment)["inferredType"]["kind"] == "array"
    direct_only_environment = {"outputs": {"state": {"sampleCount": 1, "schema": {"type": "string"}}}}
    assert validate_expression("outputs.state == 'up'", direct_only_environment)["diagnostics"] == []

    payload = WorkflowExpressionEnvironmentPayload.model_validate(environment)
    assert payload.outputs["state"].schema_.type == "string"  # type: ignore[union-attr]


def test_unscoped_output_document_projection_uses_unique_direct_fields() -> None:
    document = {
        "workflow": {
            "inputs": [],
            "nodes": [{"id": "step", "stepType": "expression", "collectionCalls": [
                {"id": "direct", "key": "", "sampleCount": 1, "definition": {"id": "one", "revision": 1}},
                {"id": "duplicate", "key": "", "sampleCount": 1, "definition": {"id": "two", "revision": 1}},
            ]}],
        },
        "collectionSnapshots": [
            {"id": "one", "revision": 1, "spec": {"collectionType": "cli"}, "outputs": [
                {"key": "state", "schema": {"type": "string"}},
                {
                    "key": "details",
                    "schema": {
                        "type": "object",
                        "title": "详情",
                        "description": "",
                        "properties": {"status": {"type": "string"}},
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                },
            ]},
            {"id": "two", "revision": 1, "spec": {"collectionType": "cli"}, "outputs": [
                {"key": "state", "schema": {"type": "boolean"}},
            ]},
        ],
    }

    environment = workflow_expression_environment(document)
    assert set(environment["outputs"]) == {"details"}
    assert environment["outputs"]["details"]["schema"]["type"] == "object"

    definitions = {(item["id"], item["revision"]): item for item in document["collectionSnapshots"]}
    step_environment = _step_expression_environment(document["workflow"]["nodes"][0], definitions, {})
    assert validate_expression("outputs.details.status == 'up'", step_environment)["diagnostics"] == []


def test_expression_reports_forbidden_and_positioned_diagnostics() -> None:
    result = validate_expression("lambda value: value", {"inputs": {}, "outputs": {}})

    assert result["diagnostics"][0]["code"] == "FORBIDDEN_LAMBDA"
    assert result["diagnostics"][0]["end"] > result["diagnostics"][0]["start"]


def test_config_expression_rejects_string_and_non_integer_subscripts() -> None:
    environment = {
        "inputs": {},
        "outputs": {},
        "config": {
            "interfaces": {
                "type": "array",
                "items": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            },
        },
    }
    string_result = validate_expression('config.interfaces["name"]', environment)
    float_result = validate_expression("config.interfaces[1.5]", environment)
    assert string_result["diagnostics"][0]["code"] == "CONFIG_STRING_SUBSCRIPT_FORBIDDEN"
    assert float_result["diagnostics"][0]["code"] == "CONFIG_ARRAY_INDEX_INVALID"


def test_nullable_config_attribute_preserves_none_type() -> None:
    result = validate_expression("config.interface.name", {"inputs": {}, "outputs": {}, "config": {
        "interface": {"type": ["object", "null"], "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }})
    assert result["inferredType"] == {"kind": "union", "options": [{"kind": "string"}, {"kind": "none"}]}


def test_config_string_subscript_is_rejected_after_array_index() -> None:
    result = validate_expression("config.interfaces[0][\"name\"]", {"inputs": {}, "outputs": {}, "config": {
        "interfaces": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}},
    }})
    assert any(item["code"] == "CONFIG_STRING_SUBSCRIPT_FORBIDDEN" for item in result["diagnostics"])


def test_config_array_slice_does_not_inherit_multi_sample_index_rule() -> None:
    result = validate_expression("config.interfaces[:].name", {"inputs": {}, "outputs": {}, "config": {
        "interfaces": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}},
    }})

    assert result["diagnostics"] == []
