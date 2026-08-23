import type { WorkflowBundle, WorkflowConclusion, WorkflowStep } from "../../types";
import { isWorkflowConclusion, isWorkflowStep } from "./domain/utils";

export type WorkflowExpressionReplaceField = "conditionExpression" | "rootCause" | "repairRecommendation";
export const workflowExpressionReplaceFields: Array<{ id: WorkflowExpressionReplaceField; label: string }> = [
  { id: "conditionExpression", label: "条件表达式" },
  { id: "rootCause", label: "故障根因" },
  { id: "repairRecommendation", label: "修复建议" },
];

export type WorkflowExpressionReplacement = {
  nodeId: string;
  nodeName: string;
  field: WorkflowExpressionReplaceField;
  fieldLabel: string;
  fieldPath: string;
  original: string;
  replaced: string;
  count: number;
  transitionId?: string;
};

export type WorkflowExpressionReplacementStats = {
  expressions: number;
  occurrences: number;
};

export function collectWorkflowExpressionReplacements(
  bundle: WorkflowBundle,
  search: string,
  replacement: string,
  fields: readonly WorkflowExpressionReplaceField[],
): WorkflowExpressionReplacement[] {
  if (!search || fields.length === 0) return [];
  const selected = new Set(fields);
  const matches: WorkflowExpressionReplacement[] = [];
  bundle.workflow.nodes.forEach((node) => {
    if (isWorkflowStep(node)) collectStepMatches(node, selected, search, replacement, matches);
    else if (isWorkflowConclusion(node)) collectConclusionMatches(node, selected, search, replacement, matches);
  });
  return matches;
}

export function replacementStats(matches: readonly WorkflowExpressionReplacement[]): WorkflowExpressionReplacementStats {
  return {
    expressions: matches.length,
    occurrences: matches.reduce((sum, item) => sum + item.count, 0),
  };
}

export function applyWorkflowExpressionReplacements(bundle: WorkflowBundle, matches: readonly WorkflowExpressionReplacement[]): void {
  matches.forEach((match) => {
    const node = bundle.workflow.nodes.find((item) => item.id === match.nodeId);
    if (!node) return;
    if (match.field === "conditionExpression" && isWorkflowStep(node)) {
      const transition = node.topology.find((item) => item.id === match.transitionId);
      if (transition) transition.conditionExpression = match.replaced;
    } else if (isWorkflowConclusion(node) && match.field !== "conditionExpression") {
      node[match.field] = match.replaced;
    }
  });
}

function collectStepMatches(
  step: WorkflowStep,
  selected: Set<WorkflowExpressionReplaceField>,
  search: string,
  replacement: string,
  matches: WorkflowExpressionReplacement[],
): void {
  if (!selected.has("conditionExpression")) return;
  step.topology.forEach((transition) => {
    const original = transition.conditionExpression;
    const count = countOccurrences(original, search);
    if (!count) return;
    matches.push({ nodeId: step.id, nodeName: step.name, field: "conditionExpression", fieldLabel: "条件表达式", fieldPath: `workflow.nodes.${step.id}.topology.${transition.id}.conditionExpression`, original, replaced: original.split(search).join(replacement), count, transitionId: transition.id });
  });
}

function collectConclusionMatches(
  conclusion: WorkflowConclusion,
  selected: Set<WorkflowExpressionReplaceField>,
  search: string,
  replacement: string,
  matches: WorkflowExpressionReplacement[],
): void {
  (['rootCause', 'repairRecommendation'] as const).forEach((field) => {
    if (!selected.has(field)) return;
    const original = conclusion[field];
    const count = countOccurrences(original, search);
    if (!count) return;
    matches.push({ nodeId: conclusion.id, nodeName: conclusion.name, field, fieldLabel: field === "rootCause" ? "故障根因" : "修复建议", fieldPath: `workflow.nodes.${conclusion.id}.${field}`, original, replaced: original.split(search).join(replacement), count });
  });
}

function countOccurrences(value: string, search: string): number {
  return value.split(search).length - 1;
}
