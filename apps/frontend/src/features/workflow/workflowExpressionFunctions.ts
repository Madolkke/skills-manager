import { api } from "../../lib/api";
import type { WorkflowExpressionFunction } from "../../types";

/** 每次编辑器进入重新获取，避免管理员停用或删除后使用旧目录。 */
export function loadWorkflowExpressionFunctions(): Promise<Record<string, WorkflowExpressionFunction>> {
  return api.getWorkflowExpressionContract().then((contract) => contract.functions).catch(() => ({}));
}

/** 保留既有调用兼容；目录不再跨页面缓存。 */
export function resetWorkflowExpressionFunctions(): void {}
