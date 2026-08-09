from __future__ import annotations

from copy import deepcopy

import pytest

from skillhub.models.errors import FieldInvariantError
from skillhub.models.rules.workflow_agent import WorkflowAgentDebugCaseProposal, validate_generated_debug_case_proposal
from skillhub.models.rules.workflow_agent_context import build_workflow_agent_context, workflow_agent_draft_digest
from skillhub.models.rules.workflows import normalize_workflow_document
from tests.executor_workflow_fixture import executor_workflow_document


def test_context_is_step_scoped_and_includes_raw_collection_samples() -> None:
    document = normalize_workflow_document(executor_workflow_document(suffix="-agent"))
    selected = document["workflow"]["nodes"][0]
    context = build_workflow_agent_context(
        document,
        selection={"type": "step", "id": selected["id"], "section": "collections"},
        existing_cases=[{"id": "case-1"}],
        recent_history=[{"agent_id": "workflow_assistant", "user_input": "说明", "response_text": "结果"}],
    )

    references = {(call["definition"]["id"], call["definition"]["revision"]) for call in selected["collectionCalls"]}
    actual = {(item["id"], item["revision"]) for item in context["collectionSnapshots"]}
    assert actual == references
    assert context["selectedStep"]["id"] == selected["id"]
    assert context["rawSamplesIncluded"] is True
    assert context["existingDebugCases"] == [{"id": "case-1"}]
    assert context["collectionSnapshotScope"]["documentTotal"] == len(document["collectionSnapshots"])
    summary = next(item for item in context["workflow"]["nodes"] if item["id"] == selected["id"])
    assert [item["id"] for item in summary["collectionCalls"]] == [item["id"] for item in selected["collectionCalls"]]
    assert summary["transitions"][0]["conditionExpression"] == selected["topology"][0]["conditionExpression"]


def test_draft_digest_is_deterministic_and_changes_with_content() -> None:
    document = executor_workflow_document(suffix="-digest")
    reordered = {key: document[key] for key in reversed(document)}
    assert workflow_agent_draft_digest(document) == workflow_agent_draft_digest(reordered)
    changed = deepcopy(document)
    changed["workflow"]["metadata"]["name"] = "changed"
    assert workflow_agent_draft_digest(document) != workflow_agent_draft_digest(changed)


def test_debug_case_proposal_must_cover_every_direct_target() -> None:
    document = executor_workflow_document(suffix="-proposal")
    step = document["workflow"]["nodes"][0]
    targets = [transition["target"]["id"] for transition in step["topology"]]
    proposal = WorkflowAgentDebugCaseProposal.model_validate(
        {
            "candidates": [
                {
                    "step_id": step["id"],
                    "name": f"target {target}",
                    "expected_target_id": target,
                    "workflow_inputs": {},
                    "collection_fixtures": {},
                }
                for target in targets
            ]
        }
    )
    validate_generated_debug_case_proposal(document, proposal, selected_step_id=step["id"])

    with pytest.raises(FieldInvariantError, match="未覆盖"):
        validate_generated_debug_case_proposal(
            document,
            WorkflowAgentDebugCaseProposal(candidates=proposal.candidates[:-1]),
            selected_step_id=step["id"],
        )
