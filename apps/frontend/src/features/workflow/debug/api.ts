import { apiDelete, apiGet, apiSend } from "../../../lib/api";
import type {
  WorkflowDebugCase,
  WorkflowDebugCasePayload,
  WorkflowDebugRun,
  WorkflowDebugRunHistory,
  WorkflowDebugRunStart,
} from "../../../types";

export const workflowDebugApi = {
  listCases(skillId: string, stepId: string, signal?: AbortSignal): Promise<WorkflowDebugCase[]> {
    const query = new URLSearchParams({ step_id: stepId });
    return apiGet(`/api/skills/${encodeURIComponent(skillId)}/workflow/debug-cases?${query}`, { signal });
  },

  createCase(skillId: string, payload: WorkflowDebugCasePayload): Promise<WorkflowDebugCase> {
    return apiSend(`/api/skills/${encodeURIComponent(skillId)}/workflow/debug-cases`, "POST", payload);
  },

  updateCase(caseId: string, payload: Partial<WorkflowDebugCasePayload>): Promise<WorkflowDebugCase> {
    const update = { ...payload };
    delete update.step_id;
    return apiSend(`/api/workflow-debug-cases/${encodeURIComponent(caseId)}`, "PATCH", update);
  },

  deleteCase(caseId: string): Promise<{ deleted: boolean }> {
    return apiDelete(`/api/workflow-debug-cases/${encodeURIComponent(caseId)}`);
  },

  startRun(caseId: string): Promise<WorkflowDebugRunStart> {
    return apiSend(`/api/workflow-debug-cases/${encodeURIComponent(caseId)}/runs`, "POST", {});
  },

  getRun(runId: string, signal?: AbortSignal): Promise<WorkflowDebugRun> {
    return apiGet(`/api/workflow-debug-runs/${encodeURIComponent(runId)}`, { signal });
  },

  advanceRun(runId: string, signal?: AbortSignal): Promise<WorkflowDebugRun> {
    return apiSend(`/api/workflow-debug-runs/${encodeURIComponent(runId)}/advance`, "POST", {}, { signal });
  },

  listRuns(caseId: string, cursor?: string | null, limit = 10): Promise<WorkflowDebugRunHistory> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return apiGet(`/api/workflow-debug-cases/${encodeURIComponent(caseId)}/runs?${query}`);
  },
};

export type WorkflowDebugApi = typeof workflowDebugApi;
