import type { WorkflowImportBundle } from "../../types";

export type WorkflowImportCandidate = {
  fileName: string;
  payload: WorkflowImportBundle;
  workflowName: string;
  stepCount: number;
  conclusionCount: number;
  collectionCount: number;
};

export function parseWorkflowImportFile(source: string, fileName: string): WorkflowImportCandidate {
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch {
    throw new Error("所选文件不是合法的 JSON。请检查文件内容后重试。");
  }
  if (!isRecord(value) || value.documentType !== "workflow_import_bundle") {
    throw new Error("所选文件不是 Workflow 可移植导入包。");
  }
  const workflow = value.workflow;
  const collections = value.collections;
  if (!isRecord(workflow) || !isRecord(workflow.metadata) || !Array.isArray(workflow.nodes) || !Array.isArray(collections)) {
    throw new Error("Workflow 导入包缺少 workflow、nodes 或 collections 结构。");
  }
  const nodes = workflow.nodes.filter(isRecord);
  return {
    fileName,
    payload: value as WorkflowImportBundle,
    workflowName: typeof workflow.metadata.name === "string" && workflow.metadata.name.trim()
      ? workflow.metadata.name
      : "未命名 Workflow",
    stepCount: nodes.filter((node) => node.stepType === "expression" || node.stepType === "script").length,
    conclusionCount: nodes.filter((node) => node.nodeType === "conclusion").length,
    collectionCount: collections.length,
  };
}

export function downloadWorkflowBundle(bundle: WorkflowImportBundle, fileName: string): void {
  const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
