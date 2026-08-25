import { api } from "../../lib/api";
import type { WorkflowExpressionFunction } from "../../types";

let catalogPromise: Promise<Record<string, WorkflowExpressionFunction>> | null = null;

export function loadWorkflowExpressionFunctions(): Promise<Record<string, WorkflowExpressionFunction>> {
  if (!catalogPromise) {
    catalogPromise = api.getWorkflowExpressionContract().then((contract) => contract.functions).catch(() => ({}));
  }
  return catalogPromise;
}

export function resetWorkflowExpressionFunctions(): void {
  catalogPromise = null;
}
