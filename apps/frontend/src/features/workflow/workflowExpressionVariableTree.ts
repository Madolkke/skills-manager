import type { WorkflowExpressionVariable } from "./workflowExpressionVariables";

export type WorkflowExpressionVariableTreeNode = {
  id: string;
  label: string;
  reference: string;
  dataType: string;
  source: string;
  kind: WorkflowExpressionVariable["kind"] | "namespace";
  children: WorkflowExpressionVariableTreeNode[];
  variable?: WorkflowExpressionVariable;
};

const segmentPattern = /[^.[\]]+|\[\d+\]/gu;

export function buildWorkflowExpressionVariableTree(
  variables: readonly WorkflowExpressionVariable[],
): WorkflowExpressionVariableTreeNode[] {
  const roots: WorkflowExpressionVariableTreeNode[] = [];
  const byReference = new Map<string, WorkflowExpressionVariableTreeNode>();
  variables.forEach((variable) => {
    const segments = variable.reference.match(segmentPattern) ?? [];
    let parent: WorkflowExpressionVariableTreeNode | undefined;
    let reference = "";
    segments.forEach((segment, index) => {
      reference = index === 0 ? segment : `${reference}${segment.startsWith("[") ? segment : `.${segment}`}`;
      let node = byReference.get(reference);
      if (!node) {
        node = {
          id: `variable-tree:${reference}`,
          label: segment,
          reference,
          dataType: "命名空间",
          source: "",
          kind: "namespace",
          children: [],
        };
        byReference.set(reference, node);
        if (parent) parent.children.push(node);
        else roots.push(node);
      }
      parent = node;
    });
    const leaf = byReference.get(variable.reference);
    if (leaf) {
      leaf.dataType = variable.dataType;
      leaf.source = variable.source;
      leaf.kind = variable.kind;
      leaf.variable = variable;
    }
  });
  return roots;
}

export function workflowExpressionVariableDefaultExpanded(
  roots: readonly WorkflowExpressionVariableTreeNode[],
): Set<string> {
  const expanded = new Set<string>();
  const visit = (node: WorkflowExpressionVariableTreeNode, depth: number): void => {
    if (!node.children.length) return;
    if (depth <= 2 || (node.reference === "topo.devices" || node.reference.startsWith("topo.devices."))) expanded.add(node.reference);
    node.children.forEach((child) => visit(child, depth + 1));
  };
  roots.forEach((root) => visit(root, 1));
  return expanded;
}
