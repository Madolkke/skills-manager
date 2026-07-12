import type { WorkflowSyncStatus } from "../../../types";

export function workflowStatusLabel(status: WorkflowSyncStatus): string {
  if (status === "never_synced") return "尚未同步";
  if (status === "in_sync") return "已同步";
  if (status === "workflow_changed") return "Workflow 已更新";
  if (status === "skill_changed") return "Skill 已手动更新";
  return "两侧均有更新";
}

export function workflowStatusTone(status: WorkflowSyncStatus): "neutral" | "success" | "warning" | "danger" {
  if (status === "in_sync") return "success";
  if (status === "never_synced") return "neutral";
  if (status === "workflow_changed") return "warning";
  return "danger";
}
