import { describe, expect, it } from "vitest";
import { buildWorkflowExpressionVariableTree, workflowExpressionVariableDefaultExpanded } from "./workflowExpressionVariableTree";
import type { WorkflowExpressionVariable } from "./workflowExpressionVariables";

describe("workflow expression variable tree", () => {
  it("groups flat references and expands roots plus first-level objects", () => {
    const variables: WorkflowExpressionVariable[] = [
      variable("outputs.status", "string", "步骤 · 状态"),
      variable("outputs.interface", "object", "步骤 · 接口"),
      variable("outputs.interface.name", "string", "步骤 · 接口"),
      variable("outputs.interface.details", "object", "步骤 · 接口"),
      variable("outputs.interface.details.speed", "integer", "步骤 · 接口"),
      variable("topo.devices.primary", "object", "设备角色"),
      variable("topo.devices.primary.ip", "string", "设备角色"),
    ];
    const tree = buildWorkflowExpressionVariableTree(variables);
    expect(tree.map((item) => item.reference)).toEqual(["outputs", "topo"]);
    expect(tree[0]?.children.map((item) => item.reference)).toEqual(["outputs.status", "outputs.interface"]);
    const expanded = workflowExpressionVariableDefaultExpanded(tree);
    expect(expanded.has("outputs")).toBe(true);
    expect(expanded.has("outputs.interface")).toBe(true);
    expect(expanded.has("outputs.interface.details")).toBe(false);
    expect(expanded.has("topo.devices.primary")).toBe(true);
  });
});

function variable(reference: string, dataType: string, source: string): WorkflowExpressionVariable {
  return { id: reference, reference, kind: "output", name: reference, dataType, source, aliases: [] };
}
