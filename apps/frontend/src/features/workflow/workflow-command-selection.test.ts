import { describe, expect, it } from "vitest";
import type { CommandLibrarySearchResult, WorkflowBundle, WorkflowDetail } from "../../types";
import { useWorkflowEditor } from "./useWorkflowEditor";

describe("workflow command selection", () => {
  it("步骤内物化命令时不切换到采集库选择", () => {
    const editor = useWorkflowEditor(() => false);
    editor.load({ document: bundle() } as WorkflowDetail, []);

    const definition = editor.addCommandLibraryResult(command(), { selectCollection: false });
    expect(definition).toBeTruthy();
    expect(editor.selection.value).toEqual({ type: "metadata" });

    const callId = editor.addCall("step-1", definition!);
    const step = editor.bundle.value?.workflow.nodes.find((node) => node.id === "step-1");
    expect(callId).toBeTruthy();
    expect("stepType" in step! && step.collectionCalls[0]?.definition).toEqual({ id: definition!.id, revision: definition!.revision });
  });

  it("采集库入口仍可选中物化后的定义", () => {
    const editor = useWorkflowEditor(() => false);
    editor.load({ document: bundle() } as WorkflowDetail, []);

    const definition = editor.addCommandLibraryResult(command());
    expect(definition).toBeTruthy();
    expect(editor.selection.value).toEqual({ type: "collection", id: definition!.id, revision: definition!.revision });
  });
});

function command(): CommandLibrarySearchResult {
  return {
    id: "system-status",
    source: "system",
    key: "show_status",
    name: "状态",
    expression: "show status",
    metadata: { name: "状态", description: "", industry: "", device: "", versions: [], tags: [] },
    samples: [],
    outputSchema: { type: "object", properties: { status: { type: "string" } }, required: ["status"], additionalProperties: false },
  };
}

function bundle(): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "测试", code: "", description: "", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [{ id: "step-1", name: "检查", description: "", isStart: true, stepType: "expression", collectionCalls: [], topology: [] }],
    },
    collectionSnapshots: [],
  };
}
