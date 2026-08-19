import type { CollectionCall, WorkflowBundle, WorkflowStep } from "../../types";
import { workflowSteps } from "./domain/utils";

/**
 * Returns the steps whose outputs can be referenced from an expression owned by
 * `sourceStepId`. The graph is traversed backwards so node array order does
 * not affect reachability; the final list is restored to document order for
 * stable completion and first-wins behavior.
 */
export function workflowExpressionVisibleSteps(bundle: WorkflowBundle, sourceStepId?: string): WorkflowStep[] {
  const steps = workflowSteps(bundle);
  if (sourceStepId === undefined) return steps;

  const byId = new Map(steps.map((step) => [step.id, step]));
  if (!byId.has(sourceStepId)) return [];

  const visibleIds = new Set<string>([sourceStepId]);
  const pending = [sourceStepId];
  while (pending.length > 0) {
    const targetId = pending.pop();
    if (!targetId) continue;
    steps.forEach((candidate) => {
      if (candidate.topology.some((transition) => transition.target.id === targetId) && !visibleIds.has(candidate.id)) {
        visibleIds.add(candidate.id);
        pending.push(candidate.id);
      }
    });
  }

  return steps.filter((step) => visibleIds.has(step.id));
}

export type WorkflowBindingCall = { call: CollectionCall; step: WorkflowStep };

/** Return calls available to a binding on the current call. */
export function workflowBindingVisibleCalls(bundle: WorkflowBundle, sourceStepId: string, currentCallId: string): WorkflowBindingCall[] {
  const visibleSteps = workflowExpressionVisibleSteps(bundle, sourceStepId);
  const result: WorkflowBindingCall[] = [];
  for (const step of visibleSteps) {
    for (const call of step.collectionCalls) {
      if (step.id === sourceStepId && call.id === currentCallId) break;
      result.push({ call, step });
    }
  }
  return result;
}
