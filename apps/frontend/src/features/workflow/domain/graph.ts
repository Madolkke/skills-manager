import type { WorkflowBundle } from "../../../types";
import { workflowConclusions, workflowSteps } from "./utils";

export type WorkflowGraphProjection = {
  nodes: Array<{ id: string; type: "step" | "conclusion"; label: string; isStart?: boolean }>;
  edges: Array<{ id: string; source: string; target: string; label: string; loop: boolean }>;
};

export function projectWorkflowGraph(bundle: WorkflowBundle): WorkflowGraphProjection {
  const steps = workflowSteps(bundle);
  const nodes = [
    ...steps.map((step) => ({ id: step.id, type: "step" as const, label: step.name, isStart: step.isStart })),
    ...workflowConclusions(bundle).map((item) => ({ id: item.id, type: "conclusion" as const, label: item.name })),
  ];
  const adjacency = new Map(steps.map((step) => [step.id, step.topology.map((item) => item.target.id)]));
  const edges = steps.flatMap((step) => step.topology.map((item) => ({
    id: item.id,
    source: step.id,
    target: item.target.id,
    label: item.conditionText || "无条件",
    loop: hasPath(item.target.id, step.id, adjacency),
  })));
  return { nodes, edges };
}

export function reachableNodeIds(bundle: WorkflowBundle): Set<string> {
  const steps = workflowSteps(bundle);
  const byId = new Map(steps.map((step) => [step.id, step]));
  const queue = steps.filter((step) => step.isStart).map((step) => step.id);
  const reached = new Set<string>();
  while (queue.length) {
    const id = queue.shift();
    if (!id || reached.has(id)) continue;
    reached.add(id);
    byId.get(id)?.topology.forEach((item) => queue.push(item.target.id));
  }
  return reached;
}

function hasPath(start: string, goal: string, adjacency: Map<string, string[]>): boolean {
  const queue = [start];
  const visited = new Set<string>();
  while (queue.length) {
    const id = queue.shift();
    if (!id || visited.has(id)) continue;
    if (id === goal) return true;
    visited.add(id);
    queue.push(...(adjacency.get(id) ?? []));
  }
  return false;
}
