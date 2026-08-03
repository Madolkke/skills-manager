import { onBeforeUnmount, ref } from "vue";
import { ApiError } from "../../../lib/api";
import type { WorkflowDebugCase, WorkflowDebugCasePayload, WorkflowDebugRun } from "../../../types";
import { workflowDebugApi, type WorkflowDebugApi } from "./api";
import { workflowDebugRunActive } from "./presentation";

type DebugClient = Pick<WorkflowDebugApi,
  "listCases" | "createCase" | "updateCase" | "deleteCase" | "startRun" | "advanceRun" | "listRuns">;

export type WorkflowStepDebugOptions = {
  skillId: () => string;
  stepId: () => string;
  client?: DebugClient;
  pollInterval?: number;
};

export function resolveWorkflowDebugPollInterval(raw?: string): number {
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed >= 500 ? parsed : 2000;
}

export function useWorkflowStepDebug(options: WorkflowStepDebugOptions) {
  const client = options.client ?? workflowDebugApi;
  const cases = ref<WorkflowDebugCase[]>([]);
  const history = ref<WorkflowDebugRun[]>([]);
  const currentRun = ref<WorkflowDebugRun | null>(null);
  const nextCursor = ref<string | null>(null);
  const loading = ref(false);
  const saving = ref(false);
  const deleting = ref(false);
  const starting = ref(false);
  const advancing = ref(false);
  const historyLoading = ref(false);
  const error = ref("");
  const notice = ref("");
  let stopped = false;
  let timer: number | undefined;
  let advancePromise: Promise<WorkflowDebugRun | null> | null = null;
  let advanceController: AbortController | null = null;
  let advanceToken = 0;
  let runGeneration = 0;
  let historyRequest = 0;

  onBeforeUnmount(stop);

  async function loadCases(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      cases.value = await client.listCases(options.skillId(), options.stepId());
    } catch (caught) {
      error.value = debugErrorMessage(caught, "调试例加载失败。");
    } finally {
      loading.value = false;
    }
  }

  async function saveCase(payload: WorkflowDebugCasePayload, caseId?: string): Promise<WorkflowDebugCase | null> {
    saving.value = true;
    error.value = "";
    try {
      const saved = caseId
        ? await client.updateCase(caseId, payload)
        : await client.createCase(options.skillId(), payload);
      const index = cases.value.findIndex((item) => item.id === saved.id);
      if (index < 0) cases.value.push(saved);
      else cases.value.splice(index, 1, saved);
      notice.value = caseId ? "调试例已更新。" : "调试例已创建。";
      return saved;
    } catch (caught) {
      error.value = debugErrorMessage(caught, "调试例保存失败。");
      return null;
    } finally {
      saving.value = false;
    }
  }

  async function deleteCase(caseId: string): Promise<boolean> {
    deleting.value = true;
    error.value = "";
    try {
      await client.deleteCase(caseId);
      cases.value = cases.value.filter((item) => item.id !== caseId);
      notice.value = "调试例已删除。";
      return true;
    } catch (caught) {
      error.value = debugErrorMessage(caught, "调试例删除失败。");
      return false;
    } finally {
      deleting.value = false;
    }
  }

  async function startRun(caseId: string): Promise<WorkflowDebugRun | null> {
    const generation = ++runGeneration;
    starting.value = true;
    error.value = "";
    stopPolling();
    try {
      const result = await client.startRun(caseId);
      if (stopped || generation !== runGeneration) return null;
      currentRun.value = result.run;
      upsertHistory(result.run);
      notice.value = result.reused ? "已返回当前未结束的调试运行。" : "单步调试已启动。";
      scheduleAdvance();
      return result.run;
    } catch (caught) {
      if (!stopped && generation === runGeneration) error.value = debugErrorMessage(caught, "单步调试启动失败。");
      return null;
    } finally {
      starting.value = false;
    }
  }

  function advanceRun(runId = currentRun.value?.id): Promise<WorkflowDebugRun | null> {
    if (!runId) return Promise.resolve(null);
    if (advancePromise) return advancePromise;
    stopPolling();
    const generation = runGeneration;
    const token = ++advanceToken;
    const controller = new AbortController();
    advanceController = controller;
    advancing.value = true;
    error.value = "";
    advancePromise = client.advanceRun(runId, controller.signal)
      .then((run) => {
        if (stopped || generation !== runGeneration) return null;
        if (currentRun.value?.id === run.id) currentRun.value = run;
        upsertHistory(run);
        return run;
      })
      .catch((caught: unknown) => {
        if (!stopped && generation === runGeneration) error.value = debugErrorMessage(caught, "调试状态推进失败。");
        return null;
      })
      .finally(() => {
        if (token !== advanceToken) return;
        advancing.value = false;
        advancePromise = null;
        advanceController = null;
        scheduleAdvance();
      });
    return advancePromise;
  }

  async function loadHistory(caseId: string, reset = true): Promise<void> {
    const request = ++historyRequest;
    historyLoading.value = true;
    error.value = "";
    try {
      const result = await client.listRuns(caseId, reset ? null : nextCursor.value);
      if (request !== historyRequest || stopped) return;
      history.value = reset ? result.items : mergeRuns(history.value, result.items);
      nextCursor.value = result.next_cursor;
      if (reset) {
        cancelAdvance();
        runGeneration += 1;
        currentRun.value = result.items[0] ?? null;
        stopPolling();
        scheduleAdvance();
      }
    } catch (caught) {
      if (!stopped && request === historyRequest) error.value = debugErrorMessage(caught, "调试历史加载失败。");
    } finally {
      if (request === historyRequest) historyLoading.value = false;
    }
  }

  function selectRun(run: WorkflowDebugRun): void {
    cancelAdvance();
    runGeneration += 1;
    currentRun.value = run;
    stopPolling();
    scheduleAdvance();
  }

  function clearRun(): void {
    cancelAdvance();
    runGeneration += 1;
    historyRequest += 1;
    stopPolling();
    history.value = [];
    nextCursor.value = null;
    currentRun.value = null;
  }

  function stopPolling(): void {
    if (timer !== undefined) window.clearTimeout(timer);
    timer = undefined;
  }

  function cancelAdvance(): void {
    advanceToken += 1;
    advanceController?.abort();
    advanceController = null;
    advancePromise = null;
    advancing.value = false;
  }

  function stop(): void {
    stopped = true;
    cancelAdvance();
    runGeneration += 1;
    historyRequest += 1;
    stopPolling();
  }

  function scheduleAdvance(): void {
    stopPolling();
    if (stopped || !workflowDebugRunActive(currentRun.value)) return;
    const configuredInterval = currentRun.value?.poll_interval_seconds;
    const interval = options.pollInterval
      ?? resolveWorkflowDebugPollInterval(configuredInterval === undefined ? undefined : String(configuredInterval * 1000));
    timer = window.setTimeout(() => void advanceRun(), interval);
  }

  function upsertHistory(run: WorkflowDebugRun): void {
    const index = history.value.findIndex((item) => item.id === run.id);
    if (index < 0) history.value.unshift(run);
    else history.value.splice(index, 1, run);
  }

  return {
    cases, history, currentRun, nextCursor, loading, saving, deleting, starting, advancing,
    historyLoading, error, notice, loadCases, saveCase, deleteCase, startRun, advanceRun,
    loadHistory, selectRun, clearRun, stop,
  };
}

function mergeRuns(existing: WorkflowDebugRun[], incoming: WorkflowDebugRun[]): WorkflowDebugRun[] {
  const merged = new Map(existing.map((run) => [run.id, run]));
  incoming.forEach((run) => merged.set(run.id, run));
  return [...merged.values()];
}

function debugErrorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}
