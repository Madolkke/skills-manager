from copy import deepcopy

import pytest

from skillhub.models.rules.executor_workflows import convert_workflow_document, project_workflow_document
from skillhub.models.rules.workflows import generate_workflow_skill, normalize_workflow_document, validate_workflow_document
from skillhub.models.rules.workflows.export_schema import export_workflow_import_bundle
from skillhub.models.rules.workflows.generators.documents import render_collection_reference
from skillhub.models.rules.workflows.import_schema import validate_workflow_import_references
from tests.executor_workflow_fixture import executor_workflow_document


def function_document() -> dict:
    document = executor_workflow_document()
    definition = document["collectionSnapshots"][0]
    definition["spec"] = {
        "collectionType": "function",
        "language": "python",
        "source": "def broken(:\n    return '中文 / 任意文本'\n",
    }
    definition["inputs"][3]["required"] = False
    definition["inputs"][4]["required"] = False
    definition["outputs"].append({
        "id": "output-details",
        "key": "details",
        "required": True,
        "schema": {
        "type": "object",
        "title": "计算结果",
        "description": "递归结构",
        "properties": {
            "ratio": {"type": "number", "title": "比例", "description": ""},
            "labels": {
                "type": "array",
                "title": "标签",
                "description": "",
                "items": {"type": "string", "title": "标签", "description": ""},
            },
        },
        "required": ["ratio"],
        "additionalProperties": False,
        },
    })
    document["workflow"]["nodes"][0]["collectionCalls"][1]["inputBindings"]["parameter-memory"]["reference"] = {
        "call_id": "call-environment",
        "output_id": "output-memory",
    }
    return normalize_workflow_document(document)


def test_function_source_and_recursive_schema_round_trip_without_python_validation() -> None:
    document = function_document()
    document["workflow"]["nodes"][0]["topology"][0]["conditionExpression"] = "outputs.details.ratio > 0"

    assert not [item for item in validate_workflow_document(document) if item["severity"] == "error"]
    assert document["collectionSnapshots"][0]["spec"]["source"].startswith("def broken(:")
    assert document["collectionSnapshots"][0]["outputs"][1]["schema"]["properties"]["labels"]["type"] == "array"


def test_function_output_binds_to_later_collection_and_is_preserved_by_generators() -> None:
    document = function_document()
    assert convert_workflow_document(deepcopy(document)).steps[0].collections[0].inputs[0].value == "outputs.memory-percentage"

    collection = render_collection_reference(document["collectionSnapshots"][0])
    assert "```python" in collection
    assert "def broken(:" in collection
    for generator_id in ("builtin.single-file", "builtin.three-file", "builtin.node-split", "builtin.cli-workflow"):
        result = generate_workflow_skill(slug="function-workflow", document=document, generator_id=generator_id, generator_options={})
        text = "\n".join(file.content_text for file in result.files)
        assert "def broken(:" in text
        assert "```python" in text


def test_function_spec_survives_portable_import_export() -> None:
    document = function_document()

    portable = export_workflow_import_bundle(document).model_dump(mode="json", by_alias=True, exclude_none=True)
    validate_workflow_import_references(portable)

    function = portable["collections"][0]
    assert function["spec"] == document["collectionSnapshots"][0]["spec"]


def test_function_call_is_filtered_from_executor_ids_but_referenced_path_is_unchanged() -> None:
    document = function_document()

    projection = project_workflow_document(document)

    assert dict(projection.id_map.call_ids) == {("step-prepare", "call-check"): 4}
    assert projection.workflow.steps[0].collections[0].inputs[0].value == "outputs.memory-percentage"
    assert projection.workflow.conclusions[0].id == 8


@pytest.mark.parametrize("source", ["", "   \n\t", "raise SyntaxError('保存即可')\n结果 = '中文'"])
def test_function_source_accepts_any_text(source: str) -> None:
    document = function_document()
    document["collectionSnapshots"][0]["spec"]["source"] = source

    normalized = normalize_workflow_document(document)

    assert normalized["collectionSnapshots"][0]["spec"]["source"] == source
