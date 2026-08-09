import { getActorId } from "../../../lib/identity";
import { apiDelete, apiGet, apiSend } from "../../../lib/api";
import { API_BASE_URL } from "../../../lib/api/httpClient";
import type {
  StartWorkflowAgentRun,
  WorkflowAgentApplyResult,
  WorkflowAgentCatalog,
  WorkflowAgentEvent,
  WorkflowAgentRun,
  WorkflowAgentSession,
  WorkflowDebugCasePayload,
} from "../../../types";

export const workflowAgentApi = {
  catalog(skillId: string): Promise<WorkflowAgentCatalog> {
    return apiGet(`/api/skills/${encodeURIComponent(skillId)}/workflow/agents`);
  },
  listSessions(skillId: string): Promise<WorkflowAgentSession[]> {
    return apiGet(`/api/skills/${encodeURIComponent(skillId)}/workflow/agent-sessions`);
  },
  createSession(skillId: string): Promise<WorkflowAgentSession> {
    return apiSend(`/api/skills/${encodeURIComponent(skillId)}/workflow/agent-sessions`, "POST", { title: "" });
  },
  archiveSession(sessionId: string): Promise<WorkflowAgentSession> {
    return apiSend(`/api/workflow-agent-sessions/${encodeURIComponent(sessionId)}/archive`, "POST", {});
  },
  deleteSession(sessionId: string): Promise<{ deleted: boolean }> {
    return apiDelete(`/api/workflow-agent-sessions/${encodeURIComponent(sessionId)}`);
  },
  listRuns(sessionId: string): Promise<WorkflowAgentRun[]> {
    return apiGet(`/api/workflow-agent-sessions/${encodeURIComponent(sessionId)}/runs`);
  },
  startRun(sessionId: string, payload: StartWorkflowAgentRun): Promise<WorkflowAgentRun> {
    return apiSend(`/api/workflow-agent-sessions/${encodeURIComponent(sessionId)}/runs`, "POST", payload);
  },
  getRun(runId: string): Promise<WorkflowAgentRun> {
    return apiGet(`/api/workflow-agent-runs/${encodeURIComponent(runId)}`);
  },
  cancelRun(runId: string): Promise<WorkflowAgentRun> {
    return apiSend(`/api/workflow-agent-runs/${encodeURIComponent(runId)}/cancel`, "POST", {});
  },
  applyProposal(proposalId: string, candidates: WorkflowDebugCasePayload[]): Promise<WorkflowAgentApplyResult> {
    return apiSend(`/api/workflow-agent-proposals/${encodeURIComponent(proposalId)}/apply`, "POST", { candidates });
  },
};

export async function streamWorkflowAgentEvents(
  runId: string,
  after: number,
  signal: AbortSignal,
  receive: (event: WorkflowAgentEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/workflow-agent-runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    credentials: "include",
    headers: { accept: "text/event-stream", "X-SkillHub-Actor": getActorId(), "Last-Event-ID": String(after) },
    signal,
  });
  if (!response.ok || !response.body) throw new Error(`助手事件流连接失败（${response.status}）。`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
      if (data) receive(JSON.parse(data) as WorkflowAgentEvent);
    }
    if (done) return;
  }
}
