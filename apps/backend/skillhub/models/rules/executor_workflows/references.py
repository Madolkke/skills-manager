from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import TypeAlias

from skillhub.models.rules.workflows.expression.environment import expression_scope_steps
from skillhub.models.rules.workflows.schema import (
    BaseStep,
    CollectionCall,
    CollectionDefinition,
    Conclusion,
    ConfigCollectionSpec,
    ExpressionStep,
    FunctionCollectionSpec,
    LogCollectionSpec,
    ScriptStep,
)

Node: TypeAlias = ExpressionStep | ScriptStep | Conclusion
ExecutorIdMaps: TypeAlias = tuple[dict[int, int], dict[tuple[int, int], int], dict[tuple[int, int], int], dict[int, int]]


def visible_output_calls(
    steps: Sequence[tuple[int, BaseStep]], step: BaseStep, current: CollectionCall, reference_id: str | None,
) -> list[tuple[int, int, CollectionCall]]:
    """Resolve visible calls without collapsing duplicate reference identities."""
    visible_ids = {
        item["id"] for item in expression_scope_steps(
            [node.model_dump(by_alias=True) for _, node in steps], step.id,
        )
    }
    matches = []
    for node_index, node in steps:
        if node.id not in visible_ids:
            continue
        for call_index, candidate in enumerate(node.collection_calls):
            if node is step and candidate is current:
                break
            if candidate.id == reference_id:
                matches.append((node_index, call_index, candidate))
    return matches


def allocate_ids(
    steps: Sequence[tuple[int, BaseStep]],
    conclusions: Sequence[tuple[int, Conclusion]],
    included_calls: set[tuple[int, int]] | None = None,
) -> ExecutorIdMaps:
    next_id = 2
    step_ids: dict[int, int] = {}
    call_ids: dict[tuple[int, int], int] = {}
    transition_ids: dict[tuple[int, int], int] = {}
    conclusion_ids: dict[int, int] = {}
    for node_index, _step in steps:
        step_ids[node_index] = next_id
        next_id += 1
    for node_index, step in steps:
        for call_index, _call in enumerate(step.collection_calls):
            if included_calls is not None and (node_index, call_index) not in included_calls:
                continue
            call_ids[(node_index, call_index)] = next_id
            next_id += 1
    for node_index, step in steps:
        for transition_index, _transition in enumerate(step.topology):
            transition_ids[(node_index, transition_index)] = next_id
            next_id += 1
    for node_index, _conclusion in conclusions:
        conclusion_ids[node_index] = next_id
        next_id += 1
    return step_ids, call_ids, transition_ids, conclusion_ids


def group_nodes(nodes: list[Node]) -> dict[str, list[tuple[int, Node]]]:
    groups: dict[str, list[tuple[int, Node]]] = defaultdict(list)
    for index, node in enumerate(nodes):
        groups[node.id].append((index, node))
    return groups


def group_definitions(definitions: list[CollectionDefinition]) -> dict[tuple[str, int], list[CollectionDefinition]]:
    groups: dict[tuple[str, int], list[CollectionDefinition]] = defaultdict(list)
    for definition in definitions:
        groups[(definition.id, definition.revision)].append(definition)
    return groups


def projected_call_indexes(
    steps: Sequence[tuple[int, BaseStep]],
    definitions: dict[tuple[str, int], list[CollectionDefinition]],
) -> set[tuple[int, int]]:
    return {
        (node_index, call_index)
        for node_index, step in steps
        for call_index, call in enumerate(step.collection_calls)
        if len(matches := definitions.get((call.definition.id, call.definition.revision), [])) == 1
        and not isinstance(matches[0].spec, (LogCollectionSpec, ConfigCollectionSpec, FunctionCollectionSpec))
    }


def output_path(call: CollectionCall, output_key: str) -> str:
    if call.key.strip():
        return f"outputs.{call.key}.{output_key}"
    return f"outputs.{output_key}"


__all__ = ["allocate_ids", "group_definitions", "group_nodes", "output_path", "projected_call_indexes"]
