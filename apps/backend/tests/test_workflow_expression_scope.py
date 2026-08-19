from __future__ import annotations

from skillhub.models.rules.workflows.expression import validate_expression
from skillhub.models.rules.workflows.expression.environment import (
    expression_scope_steps,
    workflow_expression_environment,
)
from skillhub.models.rules.workflows.validation import _step_expression_environment


def test_step_environment_uses_transitive_predecessors_and_hides_successors() -> None:
    scalar = {"type": "string"}
    details = {
        "type": "object",
        "properties": {"status": scalar},
        "required": ["status"],
        "additionalProperties": False,
    }
    definitions = {
        ("future", 1): _definition("future", "value", scalar),
        ("current", 1): _definition("current", "value", scalar),
        ("root", 1): _definition("root", "details", details),
        ("previous", 1): _definition("previous", "state", scalar),
    }
    steps = [
        _step("future-step", "future", "future", []),
        _step("current-step", "current", "current", ["future-step"]),
        _step("root-step", "", "root", ["previous-step"]),
        _step("previous-step", "", "previous", ["current-step"]),
    ]

    environment = _step_expression_environment(
        steps[1],
        definitions,
        {},
        all_steps=steps,
    )

    assert set(environment["outputs"]) == {"current", "details", "state"}
    assert "future" not in environment["outputs"]
    assert validate_expression("outputs.details.status == outputs.state", environment)["diagnostics"] == []
    assert workflow_expression_environment(
        {"workflow": {"inputs": [], "nodes": steps}, "collectionSnapshots": list(definitions.values())},
        "current-step",
    ) == environment


def test_scope_is_cycle_safe_and_preserves_document_order() -> None:
    steps = [
        _step("future", "future", "future", ["current"]),
        _step("current", "current", "current", ["future"]),
        _step("root", "root", "root", ["previous"]),
        _step("previous", "previous", "previous", ["current"]),
    ]

    assert [step["id"] for step in expression_scope_steps(steps, "current")] == [
        "future",
        "current",
        "root",
        "previous",
    ]


def test_keyed_outputs_keep_document_order_first_wins_across_steps() -> None:
    definitions = {
        ("first", 1): _definition("first", "name", {"type": "string"}),
        ("second", 1): _definition("second", "count", {"type": "integer"}),
    }
    steps = [
        _step("first", "status", "first", ["second"]),
        _step("second", "status", "second", []),
    ]

    environment = _step_expression_environment(
        steps[1],
        definitions,
        {},
        all_steps=steps,
    )

    assert set(environment["outputs"]["status"]["fields"]) == {"name"}


def test_branch_join_hides_duplicate_direct_outputs() -> None:
    definitions = {
        ("left", 1): _definition("left", "state", {"type": "string"}),
        ("right", 1): _definition("right", "state", {"type": "boolean"}),
        ("join", 1): _definition("join", "result", {"type": "string"}),
    }
    steps = [
        _step("left", "", "left", ["join"]),
        _step("right", "", "right", ["join"]),
        _step("join", "join", "join", []),
    ]

    environment = _step_expression_environment(
        steps[2],
        definitions,
        {},
        all_steps=steps,
    )

    assert "state" not in environment["outputs"]
    assert "join" in environment["outputs"]


def test_unscoped_multi_sample_call_is_not_projected() -> None:
    document = _document(
        [_step("step", "", "one", [])],
        [_definition("one", "state", {"type": "string"})],
    )
    document["workflow"]["nodes"][0]["collectionCalls"][0]["sampleCount"] = 2

    assert workflow_expression_environment(document, "step")["outputs"] == {}


def test_unscoped_multi_sample_call_keeps_config_projection() -> None:
    definition = _definition("config", "state", {"type": "string"})
    definition["spec"] = {
        "collectionType": "config",
        "config": {
            "commands": [
                {
                    "name": "interface",
                    "unique": True,
                    "captures": {},
                    "children": [],
                }
            ]
        },
    }
    document = _document([_step("step", "", "config", [])], [definition])
    document["workflow"]["nodes"][0]["collectionCalls"][0]["sampleCount"] = 2

    environment = workflow_expression_environment(document, "step")

    assert environment["outputs"] == {}
    assert set(environment["config"]) == {"interface"}


def _definition(definition_id: str, output_key: str, schema: dict) -> dict:
    return {
        "id": definition_id,
        "revision": 1,
        "spec": {"collectionType": "cli"},
        "outputs": [{"key": output_key, "schema": schema}],
    }


def _step(step_id: str, call_key: str, definition_id: str, targets: list[str]) -> dict:
    return {
        "id": step_id,
        "stepType": "expression",
        "collectionCalls": [
            {
                "id": f"call-{step_id}",
                "key": call_key,
                "sampleCount": 1,
                "definition": {"id": definition_id, "revision": 1},
            }
        ],
        "topology": [
            {"id": f"path-{step_id}-{target}", "target": {"id": target}}
            for target in targets
        ],
    }


def _document(steps: list[dict], definitions: list[dict]) -> dict:
    return {
        "workflow": {"inputs": [], "nodes": steps},
        "collectionSnapshots": definitions,
    }
