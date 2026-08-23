from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import Field

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.document_migration import migrate_output_v3, migrate_parameter_v3
from skillhub.models.rules.workflows.expression.environment import binding_scope_calls, conclusion_scope_steps, project_workflow_expression_environment
from skillhub.models.rules.workflows.schema import (
    Binding,
    CollectionMetadata,
    CollectionOutput,
    CollectionSpec,
    Conclusion,
    DeviceRole,
    Parameter,
    ScriptDraft,
    Transition,
    WorkflowMetadata,
    WorkflowModel,
    _normalize,
)
from skillhub.models.rules.workflows.templates import validate_template


class ImportCollectionDefinition(WorkflowModel):
    local_id: str
    key: str
    metadata: CollectionMetadata
    spec: CollectionSpec
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[CollectionOutput] = Field(default_factory=list)


class ImportCollectionCall(WorkflowModel):
    id: str
    key: str
    name: str
    definition_local_id: str
    device_role_id: str | None = None
    sample_count: int = 1
    input_bindings: dict[str, Binding] = Field(default_factory=dict)


class ImportBaseStep(WorkflowModel):
    id: str
    name: str
    description: str = ""
    is_start: bool = False
    collection_calls: list[ImportCollectionCall] = Field(default_factory=list)
    topology: list[Transition] = Field(default_factory=list)


class ImportExpressionStep(ImportBaseStep):
    step_type: Literal["expression"]


class ImportScriptStep(ImportBaseStep):
    step_type: Literal["script"]
    script: ScriptDraft | None = None


class ImportWorkflow(WorkflowModel):
    metadata: WorkflowMetadata
    inputs: list[Parameter] = Field(default_factory=list)
    device_roles: list[DeviceRole] = Field(default_factory=list)
    nodes: list[ImportExpressionStep | ImportScriptStep | Conclusion] = Field(default_factory=list)


class WorkflowImportBundle(WorkflowModel):
    document_type: Literal["workflow_import_bundle"]
    workflow: ImportWorkflow
    collections: list[ImportCollectionDefinition] = Field(default_factory=list)


def normalize_workflow_import_bundle(value: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(value)
    workflow = value.get("workflow", {})
    workflow["inputs"] = [migrate_parameter_v3(item) if "schema" not in item else item for item in workflow.get("inputs", [])]
    for definition in value.get("collections", []):
        if "localId" not in definition and "local_id" in definition:
            definition["localId"] = definition.pop("local_id")
        definition["localId"] = str(definition.get("localId", "")).strip()
        _normalize_legacy_cli_spec(definition)
        definition["inputs"] = [migrate_parameter_v3(item) if "schema" not in item else item for item in definition.get("inputs", [])]
        definition["outputs"] = [migrate_output_v3(item) if "schema" not in item else item for item in definition.get("outputs", [])]
    for node in workflow.get("nodes", []):
        for call in node.get("collectionCalls", []):
            if "definitionLocalId" not in call and "definition_local_id" in call:
                call["definitionLocalId"] = call.pop("definition_local_id")
            if "definitionLocalId" in call:
                call["definitionLocalId"] = str(call["definitionLocalId"]).strip()
    return _normalize(WorkflowImportBundle, value, "Workflow 导入文档格式不正确。")


def _normalize_legacy_cli_spec(definition: dict[str, Any]) -> None:
    spec = definition.get("spec")
    if not isinstance(spec, dict):
        return
    if "collectionType" not in spec and "collection_type" in spec:
        spec["collectionType"] = spec.pop("collection_type")
    if "sqlDialect" not in spec and "sql_dialect" in spec:
        spec["sqlDialect"] = spec.pop("sql_dialect")
    if "collectionType" not in spec and "queries" not in spec and "sqlDialect" not in spec:
        spec["collectionType"] = "cli"
    if isinstance(spec, dict) and "collectionType" not in spec and ("queries" in spec or "sqlDialect" in spec):
        spec["collectionType"] = "log"
    if isinstance(spec, dict) and spec.get("collectionType") == "log":
        spec.setdefault("sqlDialect", "duckdb")


def validate_workflow_import_references(bundle: dict[str, Any]) -> None:
    definitions = _definition_map(bundle["collections"])
    workflow = bundle["workflow"]
    nodes = workflow["nodes"]
    node_ids = {item["id"] for item in nodes}
    workflow_input_ids = {item["id"] for item in workflow["inputs"]}

    for node in nodes:
        if "stepType" not in node:
            continue
        for item in node["topology"]:
            if item["target"]["id"] not in node_ids:
                raise InvariantError(f"Workflow import transition target does not exist: {item['target']['id']}")
        for call in node["collectionCalls"]:
            local_id = call["definitionLocalId"]
            definition = definitions.get(local_id)
            if definition is None:
                raise InvariantError(f"Workflow import Collection does not exist: {local_id}")
            definition_input_ids = {item["id"] for item in definition["inputs"]}
            for input_id, binding in call["inputBindings"].items():
                if input_id not in definition_input_ids:
                    raise InvariantError(f"Workflow import Collection input does not exist: {input_id}")
                visible_calls, all_calls = binding_scope_calls(nodes, node["id"], call["id"])
                _validate_binding(binding, workflow_input_ids, visible_calls, all_calls, definitions, node["id"])

    imported_definitions = {
        (definition["localId"], 1): definition
        for definition in bundle["collections"]
    }
    projected_nodes = deepcopy(nodes)
    for projected_node in projected_nodes:
        for projected_call in projected_node.get("collectionCalls", []):
            projected_call["definition"] = {"id": projected_call["definitionLocalId"], "revision": 1}
    workflow_inputs = {
        item["key"].strip(): item["schema"]
        for item in workflow["inputs"]
        if item["key"].strip()
    }
    for conclusion in (node for node in nodes if node.get("nodeType") == "conclusion"):
        environment = project_workflow_expression_environment(
            conclusion_scope_steps(projected_nodes, conclusion["id"]),
            imported_definitions,
            workflow_inputs,
        )
        for field in ("rootCause", "repairRecommendation"):
            diagnostics = validate_template(conclusion.get(field, ""), environment)
            if diagnostics:
                raise InvariantError(
                    f"Workflow import conclusion template is invalid: {conclusion['id']} {field}: "
                    + "; ".join(item["message"] for item in diagnostics)
                )


def materialize_workflow_import(
    bundle: dict[str, Any],
    *,
    workflow_id: str,
    revision: int,
    collection_mappings: dict[str, tuple[str, int]],
) -> dict[str, Any]:
    workflow = deepcopy(bundle["workflow"])
    workflow["id"] = workflow_id
    workflow["revision"] = revision
    for node in workflow["nodes"]:
        if "stepType" not in node:
            continue
        for call in node["collectionCalls"]:
            local_id = call.pop("definitionLocalId")
            definition_id, definition_revision = collection_mappings[local_id]
            call["definition"] = {"id": definition_id, "revision": definition_revision}
    return {"documentType": "workflow_bundle", "workflow": workflow, "collectionSnapshots": []}


def _definition_map(definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        local_id = definition["localId"].strip()
        if not local_id or local_id in result:
            raise InvariantError("Workflow import Collection localId values must be non-empty and unique.")
        result[local_id] = definition
    return result


def _validate_binding(binding, workflow_inputs, calls, all_calls, definitions, current_step_id) -> None:
    kind = binding["kind"]
    reference = binding["reference"]
    valid = kind == "literal"
    if kind == "workflow_input":
        valid = reference.get("input_id") in workflow_inputs
    elif kind == "collection_output":
        entry = calls.get(reference.get("call_id"))
        call = entry["call"] if entry else None
        source_entry = all_calls.get(reference.get("call_id"))
        if call is None and source_entry and source_entry["stepId"] == current_step_id:
            raise InvariantError("Workflow import Collection output Binding cannot reference a later call.")
        definition = definitions.get(call["definitionLocalId"]) if call else None
        valid = bool(definition and any(item["id"] == reference.get("output_id") for item in definition["outputs"]))
    if not valid:
        raise InvariantError(f"Workflow import Binding reference is invalid: {kind}")
