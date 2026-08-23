// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import type { WorkflowBundle } from "../../types";
import { applyWorkflowExpressionReplacements, collectWorkflowExpressionReplacements, replacementStats } from "./workflowExpressionReplace";

describe("workflow expression replacement", () => {
  it("previews all selected fields and counts repeated literal matches", () => {
    const bundle = replacementBundle();
    const matches = collectWorkflowExpressionReplacements(bundle, "outputs.status", "outputs.peer", ["conditionExpression", "rootCause", "repairRecommendation"]);

    expect(matches.map((item) => [item.field, item.count])).toEqual([
      ["conditionExpression", 3],
      ["rootCause", 1],
      ["repairRecommendation", 1],
    ]);
    expect(replacementStats(matches)).toEqual({ expressions: 3, occurrences: 5 });
  });

  it("uses case-sensitive plain text matching and applies an atomic preview", () => {
    const bundle = replacementBundle();
    const matches = collectWorkflowExpressionReplacements(bundle, "Outputs.status", "x", ["conditionExpression"]);
    expect(matches).toHaveLength(0);

    const selected = collectWorkflowExpressionReplacements(bundle, "outputs.status", "", ["conditionExpression"]);
    applyWorkflowExpressionReplacements(bundle, selected);
    expect(bundle.workflow.nodes[0]).toMatchObject({ topology: [{ conditionExpression: " ==  &&  == \"up\"" }] });
  });
});

function replacementBundle(): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1", revision: 1,
      metadata: { name: "Replace", code: "", description: "", symptom: "", industry: "", device: "", versions: [] },
      inputs: [], deviceRoles: [], nodes: [
        { id: "step-1", name: "检查状态", description: "", isStart: true, stepType: "expression", collectionCalls: [], topology: [{ id: "path-1", target: { id: "conclusion-1" }, conditionText: "", conditionExpression: "outputs.status == outputs.status && outputs.status == \"up\"" }] },
        { id: "conclusion-1", name: "异常结论", severity: "error", rootCause: "根因 {{ outputs.status }}", repairRecommendation: "检查 outputs.status" , nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [],
  };
}
