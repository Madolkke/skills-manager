import type { CollectionCall, CollectionDefinition, WorkflowBundle, WorkflowConclusion, WorkflowNode, WorkflowStep, VersionedRef } from "../../../types";

export function createWorkflowId(prefix: string): string {
  const cryptoId = globalThis.crypto?.randomUUID?.();
  return `${prefix}_${cryptoId ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`}`;
}

export function cloneWorkflow<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function isWorkflowStep(node: WorkflowNode): node is WorkflowStep {
  return "stepType" in node;
}

export function isWorkflowConclusion(node: WorkflowNode): node is WorkflowConclusion {
  return "nodeType" in node;
}

export function workflowSteps(bundle: WorkflowBundle): WorkflowStep[] {
  return bundle.workflow.nodes.filter(isWorkflowStep);
}

export function workflowConclusions(bundle: WorkflowBundle): WorkflowConclusion[] {
  return bundle.workflow.nodes.filter(isWorkflowConclusion);
}

export function workflowPredecessors(bundle: WorkflowBundle, targetId: string): WorkflowStep[] {
  return workflowSteps(bundle).filter((step) => step.topology.some((transition) => transition.target.id === targetId));
}

export function refKey(reference: VersionedRef): string {
  return `${reference.id}@${reference.revision}`;
}

export function findCollection(definitions: CollectionDefinition[], reference: VersionedRef): CollectionDefinition | undefined {
  return definitions.find((item) => item.id === reference.id && item.revision === reference.revision);
}

export function findCall(bundle: WorkflowBundle, stepId: string, callId: string): CollectionCall | undefined {
  return workflowSteps(bundle).find((step) => step.id === stepId)?.collectionCalls.find((call) => call.id === callId);
}

export function mergeCatalog(...groups: CollectionDefinition[][]): CollectionDefinition[] {
  const merged = new Map<string, CollectionDefinition>();
  groups.flat().forEach((item) => merged.set(refKey(item), cloneWorkflow(item)));
  return [...merged.values()].sort((left, right) => left.metadata.name.localeCompare(right.metadata.name) || right.revision - left.revision);
}

export function syncSnapshots(bundle: WorkflowBundle, catalog: CollectionDefinition[]): void {
  const refs = new Map<string, VersionedRef>();
  workflowSteps(bundle).forEach((step) => step.collectionCalls.forEach((call) => refs.set(refKey(call.definition), call.definition)));
  bundle.collectionSnapshots = [...refs.values()].map((ref) => findCollection(catalog, ref)).filter((item): item is CollectionDefinition => Boolean(item)).map(cloneWorkflow);
}

export function nextUniqueKey(existing: string[], requested: string): string {
  const base = requested.trim() || "item";
  if (!existing.includes(base)) return base;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${base}_${index}`;
    if (!existing.includes(candidate)) return candidate;
  }
  return `${base}_${Date.now()}`;
}
