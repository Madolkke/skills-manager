from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.executor_workflows import convert_workflow_document
from skillhub.models.rules.workflows import (
    export_workflow_import_bundle,
    normalize_workflow_import_bundle,
)
from skillhub.models.rules.workflows.generators.cli_workflow import render_cli_workflow_reference
from skillhub.models.rules.workflows.generators.documents import render_node_reference, render_workflow_reference
from skillhub.models.rules.workflows.renderer import render_skill_markdown
from skillhub.models.rules.workflows.schema import migrate_workflow_document, normalize_workflow_document
from tests.executor_workflow_fixture import executor_workflow_document


@pytest.mark.parametrize("version", [3, 4, 5])
def test_legacy_steps_default_to_exclusive(version: int) -> None:
    """Reading existing document versions supplies the default without mutation."""
    source = executor_workflow_document()
    original = deepcopy(source)
    result = migrate_workflow_document(version, source)
    assert result["workflow"]["nodes"][0]["parallelBranches"] is False
    assert source == original


@pytest.mark.parametrize("enabled", [False, True])
def test_parallel_branches_round_trip_and_executor_projection(enabled: bool) -> None:
    """Authoring transfer preserves the flag while executor output ignores it."""
    source = executor_workflow_document()
    baseline = convert_workflow_document(source).model_dump()
    source["workflow"]["nodes"][0]["parallelBranches"] = enabled
    normalized = normalize_workflow_document(source)
    assert normalize_workflow_document(normalized) == normalized
    exported = export_workflow_import_bundle(normalized).model_dump(by_alias=True)
    imported = normalize_workflow_import_bundle(exported)
    assert imported["workflow"]["nodes"][0]["parallelBranches"] is enabled
    assert convert_workflow_document(normalized).model_dump() == baseline


@pytest.mark.parametrize("value", ["true", "false", 0, 1, None, [], {}])
def test_parallel_branches_rejects_non_boolean_values(value: object) -> None:
    """Both persistence and portable imports enforce strict booleans."""
    source = executor_workflow_document()
    exported = export_workflow_import_bundle(source).model_dump(by_alias=True)
    source["workflow"]["nodes"][0]["parallelBranches"] = value
    exported["workflow"]["nodes"][0]["parallelBranches"] = value
    with pytest.raises(InvariantError):
        normalize_workflow_document(source)
    with pytest.raises(InvariantError):
        normalize_workflow_import_bundle(exported)


@pytest.mark.parametrize("enabled", [None, False, True])
def test_generators_describe_branch_mode_without_execution_priority(enabled: bool | None) -> None:
    """All builtin layouts describe modes, including legacy documents."""
    document = normalize_workflow_document(executor_workflow_document())
    step = document["workflow"]["nodes"][0]
    if enabled is None:
        step.pop("parallelBranches")
    else:
        step["parallelBranches"] = enabled
    outputs = [
        render_skill_markdown(slug="branches", document=document),
        render_workflow_reference(document),
        render_node_reference(document, step),
        render_cli_workflow_reference(document),
    ]
    label = "非互斥（执行所有满足条件的分支）" if enabled else "互斥"
    for output in outputs:
        assert f"- 分支执行: {label}\n" in output
        assert "首个满足条件" not in output
