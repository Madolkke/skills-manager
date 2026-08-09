import { computed, onBeforeUnmount, ref, toRaw } from "vue";
import { apiErrorMessage, ApiError } from "../../../lib/api";
import type {
  StartWorkflowAgentRun,
  WorkflowAgentCatalog,
  WorkflowAgentEvent,
  WorkflowAgentRun,
  WorkflowAgentSession,
  WorkflowDebugCasePayload,
} from "../../../types";
import { streamWorkflowAgentEvents, workflowAgentApi } from "./api";

export function useWorkflowAgent(skillId: () => string) {
  const catalog = ref<WorkflowAgentCatalog | null>(null);
  const session = ref<WorkflowAgentSession | null>(null);
  const runs = ref<WorkflowAgentRun[]>([]);
  const currentRun = ref<WorkflowAgentRun | null>(null);
  const events = ref<WorkflowAgentEvent[]>([]);
  const candidates = ref<WorkflowDebugCasePayload[]>([]);
  const selectedCandidates = ref<boolean[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  const notice = ref("");
  let streamController: AbortController | null = null;

  const active = computed(() => currentRun.value && ["starting", "running"].includes(currentRun.value.status));

  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      catalog.value = await workflowAgentApi.catalog(skillId());
      const sessions = await workflowAgentApi.listSessions(skillId());
      session.value = sessions.find((item) => item.status === "active") ?? await workflowAgentApi.createSession(skillId());
      runs.value = await workflowAgentApi.listRuns(session.value.id);
      const latest = runs.value.at(-1);
      if (latest) void selectRun(latest);
    } catch (caught) {
      error.value = message(caught);
    } finally {
      loading.value = false;
    }
  }

  async function start(payload: StartWorkflowAgentRun): Promise<void> {
    if (!session.value || busy.value) return;
    busy.value = true;
    error.value = "";
    notice.value = "";
    try {
      const run = await workflowAgentApi.startRun(session.value.id, payload);
      runs.value.push(run);
      void selectRun(run);
    } catch (caught) {
      error.value = message(caught);
    } finally {
      busy.value = false;
    }
  }

  async function selectRun(run: WorkflowAgentRun): Promise<void> {
    streamController?.abort();
    currentRun.value = run;
    events.value = [];
    setProposal(run);
    streamController = new AbortController();
    const controller = streamController;
    await streamRunWithReconnect(run.id, controller);
  }

  async function streamRunWithReconnect(runId: string, controller: AbortController): Promise<void> {
    let cursor = 0;
    while (!controller.signal.aborted && currentRun.value?.id === runId) {
      try {
        error.value = "";
        await streamWorkflowAgentEvents(runId, cursor, controller.signal, (event) => {
          if (event.run_id !== currentRun.value?.id) return;
          cursor = Math.max(cursor, event.event_id);
          events.value.push(event);
        });
      } catch (caught) {
        if (controller.signal.aborted) return;
        error.value = message(caught);
      }
      if (controller.signal.aborted || currentRun.value?.id !== runId) return;
      try {
        await refreshRun(runId);
      } catch (caught) {
        if (controller.signal.aborted) return;
        error.value = message(caught);
        await waitForReconnect(controller.signal);
        continue;
      }
      if (!active.value) return;
      await waitForReconnect(controller.signal);
    }
  }

  async function refreshRun(runId: string): Promise<void> {
    const run = await workflowAgentApi.getRun(runId);
    const index = runs.value.findIndex((item) => item.id === run.id);
    if (index >= 0) runs.value[index] = run;
    if (currentRun.value?.id === run.id) {
      currentRun.value = run;
      setProposal(run);
    }
  }

  async function cancel(): Promise<void> {
    if (!currentRun.value || !active.value) return;
    busy.value = true;
    try {
      await workflowAgentApi.cancelRun(currentRun.value.id);
      notice.value = "已请求取消当前运行。";
    } catch (caught) {
      error.value = message(caught);
    } finally {
      busy.value = false;
    }
  }

  async function apply(): Promise<void> {
    const proposal = currentRun.value?.proposal;
    if (!proposal || busy.value) return;
    const chosen = candidates.value.filter((_, index) => selectedCandidates.value[index]);
    if (!chosen.length) return;
    busy.value = true;
    error.value = "";
    try {
      const result = await workflowAgentApi.applyProposal(proposal.id, chosen);
      const updatedRun = { ...currentRun.value!, proposal: result.proposal };
      const runIndex = runs.value.findIndex((item) => item.id === updatedRun.id);
      if (runIndex >= 0) runs.value[runIndex] = updatedRun;
      currentRun.value = updatedRun;
      notice.value = `已创建 ${result.created_cases.length} 个调试例。`;
    } catch (caught) {
      error.value = message(caught);
    } finally {
      busy.value = false;
    }
  }

  function updateCandidate(index: number, candidate: WorkflowDebugCasePayload): void {
    candidates.value[index] = candidate;
  }

  function setProposal(run: WorkflowAgentRun): void {
    candidates.value = run.proposal?.payload.candidates.map(cloneWorkflowAgentCandidate) ?? [];
    selectedCandidates.value = candidates.value.map(() => true);
  }

  onBeforeUnmount(() => streamController?.abort());
  return { catalog, session, runs, currentRun, events, candidates, selectedCandidates, loading, busy, error, notice, active, load, start, selectRun, cancel, apply, updateCandidate };
}

export function cloneWorkflowAgentCandidate(candidate: WorkflowDebugCasePayload): WorkflowDebugCasePayload {
  return structuredClone(toRaw(candidate));
}

function waitForReconnect(signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, 750);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

function message(error: unknown): string {
  return error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : "Workflow 助手请求失败。";
}
