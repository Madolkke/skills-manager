from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.workflows.schema import BaseStep, WorkflowBundle

WorkflowAgentScalar = str | int | float | bool | None


class WorkflowAgentCollectionFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_output: list[str] = Field(default_factory=list)
    outputs: dict[str, WorkflowAgentScalar] = Field(default_factory=dict)


class WorkflowAgentDebugCaseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    step_id: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=2000)] = ""
    expected_target_id: Annotated[str, Field(min_length=1)]
    workflow_inputs: dict[str, WorkflowAgentScalar] = Field(default_factory=dict)
    collection_fixtures: dict[str, WorkflowAgentCollectionFixture] = Field(default_factory=dict)


class WorkflowAgentDebugCaseProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidates: Annotated[list[WorkflowAgentDebugCaseCandidate], Field(min_length=1, max_length=10)]


def validate_generated_debug_case_proposal(
    document: dict[str, Any],
    proposal: WorkflowAgentDebugCaseProposal,
    *,
    selected_step_id: str,
) -> None:
    cases = [candidate.model_dump(mode="json") for candidate in proposal.candidates]
    validate_debug_case_candidates(document, cases)
    bundle = WorkflowBundle.model_validate(document)
    step = _step(bundle, selected_step_id)
    errors: list[FieldError] = []
    if any(case["step_id"] != selected_step_id for case in cases):
        errors.append(_error("candidates", "候选调试例必须全部属于当前 Step。"))
    expected_targets = {transition.target.id for transition in step.topology}
    actual_targets = {case["expected_target_id"] for case in cases}
    for target_id in sorted(expected_targets - actual_targets):
        errors.append(_error("candidates", f"缺少直接目标 {target_id} 的候选调试例。"))
    if errors:
        raise FieldInvariantError("Agent 生成的调试例未覆盖当前 Step。", errors)


def validate_debug_case_candidates(document: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    bundle = WorkflowBundle.model_validate(document)
    workflow_inputs = {item.id for item in bundle.workflow.inputs}
    definitions = {(item.id, item.revision): item for item in bundle.collection_snapshots}
    errors: list[FieldError] = []
    for index, case in enumerate(cases):
        step = _optional_step(bundle, str(case["step_id"]))
        prefix = f"candidates[{index}]"
        if step is None:
            errors.append(_error(f"{prefix}.step_id", "调试 Step 不存在或不唯一。"))
            continue
        targets = {transition.target.id for transition in step.topology}
        if case["expected_target_id"] not in targets:
            errors.append(_error(f"{prefix}.expected_target_id", "预期节点必须是当前 Step 的直接拓扑目标。"))
        for input_id in case["workflow_inputs"]:
            if input_id not in workflow_inputs:
                errors.append(_error(f"{prefix}.workflow_inputs.{input_id}", "Workflow input 已不存在。"))
        calls = {call.id: call for call in step.collection_calls}
        for call_id, fixture in case["collection_fixtures"].items():
            call = calls.get(call_id)
            if call is None:
                errors.append(_error(f"{prefix}.collection_fixtures.{call_id}", "CollectionCall 已不存在或不属于当前 Step。"))
                continue
            definition = definitions.get((call.definition.id, call.definition.revision))
            output_ids = {item.id for item in definition.outputs} if definition is not None else set()
            for output_id in fixture["outputs"]:
                if output_id not in output_ids:
                    errors.append(_error(f"{prefix}.collection_fixtures.{call_id}.outputs.{output_id}", "Collection output 已不存在。"))
    if errors:
        raise FieldInvariantError("Agent 调试例引用与当前 Workflow 不一致。", errors)


def _step(bundle: WorkflowBundle, step_id: str) -> BaseStep:
    step = _optional_step(bundle, step_id)
    if step is None:
        raise FieldInvariantError("当前 Step 不存在。", [_error("selection.id", "请选择已保存的 Workflow Step。")])
    return step


def _optional_step(bundle: WorkflowBundle, step_id: str) -> BaseStep | None:
    matches = [node for node in bundle.workflow.nodes if isinstance(node, BaseStep) and node.id == step_id]
    return matches[0] if len(matches) == 1 else None


def _error(field: str, message: str) -> FieldError:
    return FieldError(field=field, message=message, code="workflow_agent.unresolvable_reference")


__all__ = [
    "WorkflowAgentDebugCaseCandidate",
    "WorkflowAgentDebugCaseProposal",
    "validate_debug_case_candidates",
    "validate_generated_debug_case_proposal",
]
