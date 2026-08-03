from __future__ import annotations

import pytest

from skillhub.models.errors import FieldInvariantError
from skillhub.models.rules.executor_workflows import project_workflow_document
from skillhub.models.rules.workflow_debug import build_executor_identity, paused_run_input, target_reached
from tests.executor_workflow_fixture import executor_workflow_document


def _case(*, target: str = "step-confirm") -> dict:
    return {
        "step_id": "step-prepare",
        "expected_target_id": target,
        "workflow_inputs": {"input-slot": None, "input-enabled": False},
        "collection_fixtures": {
            "call-environment": {
                "raw_output": ["memory 82%"],
                "outputs": {"output-memory": 0.82},
            }
        },
    }


def test_debug_identity_uses_projection_without_changing_executor_workflow() -> None:
    document = executor_workflow_document()
    projection = project_workflow_document(document)

    identity = build_executor_identity(projection, document=document, case=_case())

    assert identity["step_id"] == 2
    assert identity["expected_target"] == {"type": "step", "id": 3}
    assert identity["workflow_input_keys"]["input-slot"] == "slot-id"
    assert identity["collections"]["call-environment"] == {
        "executor_id": 4,
        "output_keys": {"output-memory": "memory-percentage"},
    }
    assert "executor_identity" not in projection.workflow.model_dump(mode="json")


def test_debug_identity_rejects_stale_and_non_direct_references() -> None:
    document = executor_workflow_document()
    projection = project_workflow_document(document)
    stale = _case()
    stale["workflow_inputs"]["removed-input"] = "x"

    with pytest.raises(FieldInvariantError) as error:
        build_executor_identity(projection, document=document, case=stale)
    assert error.value.field_errors[0].field == "workflow_inputs.removed-input"

    non_direct = _case(target="missing-target")
    with pytest.raises(FieldInvariantError) as error:
        build_executor_identity(projection, document=document, case=non_direct)
    assert error.value.field_errors[0].field == "expected_target_id"


def test_parameter_pause_distinguishes_missing_null_false_and_default() -> None:
    identity = {"workflow_input_keys": {"input-slot": "slot-id", "input-enabled": "enabled"}}
    snapshot = {"workflow_inputs": {"input-slot": None, "input-enabled": False}}
    schema = {
        "type": "object",
        "properties": {
            "slot-id": {"type": "string"},
            "enabled": {"type": "boolean"},
            "limit": {"type": "integer", "default": 3},
        },
        "required": ["slot-id", "enabled", "limit"],
    }

    assert paused_run_input(schema, snapshot=snapshot, identity=identity) == {
        "slot-id": None,
        "enabled": False,
        "limit": 3,
    }

    with pytest.raises(ValueError, match="missing is required"):
        paused_run_input(
            {"type": "object", "properties": {"missing": {"type": "string"}}, "required": ["missing"]},
            snapshot=snapshot,
            identity=identity,
        )


def test_collection_pause_overlays_fixture_on_executor_template() -> None:
    identity = {
        "collections": {
            "call-environment": {
                "executor_id": 4,
                "output_keys": {"output-memory": "memory-percentage"},
            }
        }
    }
    snapshot = {"collection_fixtures": _case()["collection_fixtures"]}
    schema = {
        "properties": {
            "value": {
                "default": [
                    {
                        "collection_id": 4,
                        "command": "display memory",
                        "raw_output": [],
                        "inputs": {"slot": "1"},
                        "outputs": {},
                        "device_name": "device-a",
                    }
                ]
            }
        }
    }

    result = paused_run_input(schema, snapshot=snapshot, identity=identity)

    assert result["value"][0] == {
        "collection_id": 4,
        "command": "display memory",
        "raw_output": ["memory 82%"],
        "inputs": {"slot": "1"},
        "outputs": {"memory-percentage": 0.82},
        "device_name": "device-a",
    }


@pytest.mark.parametrize("step_status", ["success", "failure"])
def test_expected_step_success_or_failure_counts_as_reached(step_status: str) -> None:
    status = {"steps": [{"step_id": 3, "status": step_status}], "conclusion_ids": []}
    assert target_reached(status, {"type": "step", "id": 3}) is True
    assert target_reached({"steps": [], "conclusion_ids": [9]}, {"type": "conclusion", "id": 9}) is True
