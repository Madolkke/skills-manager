from copy import deepcopy

import pytest

from skillhub.models.errors import FieldInvariantError
from skillhub.models.rules.executor_workflows import convert_workflow_document
from skillhub.models.rules.workflows import generate_workflow_skill, normalize_workflow_document
from skillhub.models.rules.workflows.export_schema import export_workflow_import_bundle
from skillhub.models.rules.workflows.import_schema import materialize_workflow_import, validate_workflow_import_references
from skillhub.models.rules.workflows.validation import validate_workflow_document
from tests.executor_workflow_fixture import executor_workflow_document


def cross_step_document():
    """Move the existing consumer into a connected successor step."""
    document = executor_workflow_document()
    first, second, _ = document["workflow"]["nodes"]
    second["collectionCalls"].append(first["collectionCalls"].pop())
    second["isStart"] = False
    for key, value in (("parameter-unbound", 1), ("parameter-note", "note")):
        first["collectionCalls"][0]["inputBindings"][key] = {"kind": "literal", "value": value}
    for step in (first, second):
        for transition in step["topology"]:
            transition["conditionExpression"] = "True"
    return normalize_workflow_document(document)


def test_cross_step_binding_validates_roundtrips_and_converts():
    """The same valid binding must survive every authoring boundary."""
    document = cross_step_document()
    assert validate_workflow_document(document) == []
    portable = export_workflow_import_bundle(document).model_dump(by_alias=True, exclude_none=True)
    validate_workflow_import_references(portable)
    definitions = deepcopy(document["collectionSnapshots"])
    restored = materialize_workflow_import(
        portable, workflow_id=document["workflow"]["id"], revision=1,
        collection_mappings={item["localId"]: (definition["id"], definition["revision"])
                             for item, definition in zip(portable["collections"], definitions)},
    )
    restored["collectionSnapshots"] = definitions
    result = convert_workflow_document(restored)
    assert result.steps[1].collections[0].inputs[0].value == "outputs.memory-percentage"


def test_transitive_predecessor_binding_does_not_depend_on_document_order():
    """Graph reachability, rather than list order, determines available output."""
    document = cross_step_document()
    first, second, conclusion = document["workflow"]["nodes"]
    middle = deepcopy(second)
    middle.update(id="middle", name="Intermediate", collectionCalls=[])
    middle["topology"] = [{"id": "to-consumer", "target": {"id": second["id"]}, "conditionExpression": "True"}]
    first["topology"][0]["target"]["id"] = "middle"
    document["workflow"]["nodes"] = [second, middle, first, conclusion]
    document = normalize_workflow_document(document)
    assert validate_workflow_document(document) == []
    result = convert_workflow_document(document)
    assert result.steps[0].collections[0].inputs[0].value == "outputs.memory-percentage"


@pytest.mark.parametrize("generator_id", ["builtin.single-file", "builtin.three-file", "builtin.node-split", "builtin.cli-workflow"])
def test_all_generators_render_predecessor_binding(generator_id):
    """Every generator resolves an earlier step's output by its stable ID."""
    result = generate_workflow_skill(
        slug="cross-step", document=cross_step_document(), generator_id=generator_id, generator_options={},
    )
    text = "\n".join(file.content_text for file in result.files)
    assert "无效引用" not in text
    assert "- memory (`memory`): 采集“准备环境”的输出 `memory-percentage`" in text


@pytest.mark.parametrize("scenario", ["disconnected", "future", "later_call", "duplicate"])
def test_converter_rejects_out_of_scope_or_ambiguous_bindings(scenario):
    """Expanding reference lookup must not accept unrelated or ambiguous calls."""
    document = cross_step_document()
    first, second, _ = document["workflow"]["nodes"]
    if scenario == "disconnected":
        first["topology"] = []
    elif scenario == "future":
        first["topology"] = []
        second["topology"] = [{"id": "back", "target": {"id": first["id"]}, "conditionText": "", "conditionExpression": "True"}]
    elif scenario == "later_call":
        second["collectionCalls"].append(first["collectionCalls"].pop())
    else:
        first["collectionCalls"].append(deepcopy(first["collectionCalls"][0]))
    with pytest.raises(FieldInvariantError) as exc:
        convert_workflow_document(document)
    expected = "ambiguous_reference" if scenario == "duplicate" else "unresolvable_reference"
    assert any(error.code == f"executor_workflow.{expected}" for error in exc.value.field_errors)
