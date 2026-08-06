import type { WorkflowDebugRun, WorkflowDebugRunStatus } from "../../../types";

export function workflowDebugRunActive(run?: WorkflowDebugRun | null): boolean {
  return Boolean(run && ["starting", "running", "paused"].includes(run.status));
}

export function workflowDebugRunLabel(status: WorkflowDebugRunStatus): string {
  if (status === "starting") return "正在启动";
  if (status === "running") return "执行中";
  if (status === "paused") return "正在注入采集信息";
  if (status === "completed") return "已完成";
  if (status === "failed") return "执行失败";
  return "外部状态未知";
}

export function workflowDebugResultLabel(run: WorkflowDebugRun): string {
  if (run.status !== "completed") return workflowDebugRunLabel(run.status);
  return run.passed ? "跳转符合预期" : "跳转不符合预期";
}

export function workflowDebugRunTone(run: WorkflowDebugRun): "neutral" | "running" | "success" | "danger" | "warning" {
  if (run.status === "starting" || run.status === "running" || run.status === "paused") return "running";
  if (run.status === "completed") return run.passed ? "success" : "danger";
  if (run.status === "external_state_unknown") return "warning";
  return "danger";
}
