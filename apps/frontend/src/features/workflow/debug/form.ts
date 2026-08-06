import type {
  WorkflowBundle,
  WorkflowDebugCase,
  WorkflowDebugCasePayload,
  WorkflowDebugScalar,
  WorkflowJsonSchema,
  WorkflowStep,
} from "../../../types";

export type WorkflowDebugCaseDraft = WorkflowDebugCasePayload;

export function newWorkflowDebugCaseDraft(step: WorkflowStep, index: number): WorkflowDebugCaseDraft {
  return {
    step_id: step.id,
    name: `调试例 ${index + 1}`,
    description: "",
    expected_target_id: step.topology[0]?.target.id ?? "",
    workflow_inputs: {},
    collection_fixtures: {},
  };
}

export function workflowDebugCaseDraft(item: WorkflowDebugCase): WorkflowDebugCaseDraft {
  return cloneDebugValue({
    step_id: item.step_id,
    name: item.name,
    description: item.description,
    expected_target_id: item.expected_target_id,
    workflow_inputs: item.workflow_inputs,
    collection_fixtures: item.collection_fixtures,
  });
}

export function workflowDebugCasePayload(draft: WorkflowDebugCaseDraft): WorkflowDebugCasePayload {
  return {
    ...cloneDebugValue(draft),
    name: draft.name.trim(),
    description: draft.description.trim(),
  };
}

export function workflowDebugDraftValid(draft: WorkflowDebugCaseDraft, step: WorkflowStep, bundle?: WorkflowBundle): boolean {
  const targets = new Set(step.topology.map((item) => item.target.id));
  const targetExists = !bundle || bundle.workflow.nodes.some((node) => node.id === draft.expected_target_id);
  return Boolean(draft.name.trim() && targets.has(draft.expected_target_id) && targetExists);
}

export function workflowDebugDraftDirty(draft: WorkflowDebugCaseDraft, item: WorkflowDebugCase | null): boolean {
  if (!item) return true;
  return JSON.stringify(workflowDebugCasePayload(draft)) !== JSON.stringify(workflowDebugCasePayload(workflowDebugCaseDraft(item)));
}

export function workflowDebugScalarSupported(schema: WorkflowJsonSchema): boolean {
  return schema.type === "string" || schema.type === "integer" || schema.type === "number" || schema.type === "boolean";
}

export function defaultWorkflowDebugScalar(schema: WorkflowJsonSchema): WorkflowDebugScalar {
  if (schema.type === "boolean") return false;
  if (schema.type === "integer" || schema.type === "number") return 0;
  return "";
}

export function hasDebugValue(record: Record<string, WorkflowDebugScalar>, id: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, id);
}

export function workflowDebugTargetName(bundle: WorkflowBundle, id: string): string {
  return bundle.workflow.nodes.find((item) => item.id === id)?.name || "目标节点已不存在";
}

export function workflowDebugStepHasUnsupportedCollections(bundle: WorkflowBundle, step: WorkflowStep): boolean {
  return step.collectionCalls.some((call) => {
    const definitions = bundle.collectionSnapshots.filter(
      (definition) => definition.id === call.definition.id && definition.revision === call.definition.revision,
    );
    return definitions.length === 1 && ["log", "config"].includes(definitions[0]!.spec.collectionType);
  });
}

export function cloneDebugValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
