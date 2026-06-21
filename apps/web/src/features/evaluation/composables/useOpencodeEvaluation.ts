import { computed, onBeforeUnmount, ref, watch, type ComputedRef } from "vue";
import { api, ApiError } from "../../../lib/api";
import type { EvalCaseRunDetail, EvalSetCase, ToastState } from "../../../types";
import {
  isActiveRun,
  queuedRecordToDetail,
  resolveRunnerPollInterval,
  runnerState,
  summarizeOpencodeRuns,
  summarizeRunnerBoard,
} from "../lib/evalRunner";

type UseOpencodeEvaluationInput = {
  cases: ComputedRef<EvalSetCase[]>;
  skillVersionId: { value: string };
  evalSetId: ComputedRef<string>;
  ready: ComputedRef<boolean>;
  emitToast: (toast: ToastState) => void;
};

const ENVIRONMENT_TAGS: string[] = [];
const RUN_CONTEXT: Record<string, unknown> = {};

export function useOpencodeEvaluation(input: UseOpencodeEvaluationInput) {
  const opencodeRunsByCase = ref<Record<string, EvalCaseRunDetail>>({});
  const runningCaseId = ref<string | null>(null);
  const busy = ref(false);
  const polling = ref(false);
  const pollIntervalMs = resolveRunnerPollInterval(import.meta.env.VITE_OPENCODE_RUN_POLL_INTERVAL_MS);
  let pollTimer: number | null = null;

  const summary = computed(() => summarizeOpencodeRuns(input.cases.value, opencodeRunsByCase.value));
  const board = computed(() => summarizeRunnerBoard(input.cases.value, opencodeRunsByCase.value));
  const pollIntervalSeconds = computed(() => Math.round(pollIntervalMs / 1000));
  const hasActiveJobs = computed(() => Object.values(opencodeRunsByCase.value).some((run) => isActiveRun(run.eval_case_run.status)));
  const canRunFormalEvaluation = computed(
    () => !busy.value && !hasActiveJobs.value && input.cases.value.length > 0 && Boolean(input.skillVersionId.value) && Boolean(input.evalSetId.value),
  );

  watch([() => input.skillVersionId.value, input.evalSetId, input.ready], async () => {
    if (!input.ready.value || !input.skillVersionId.value || !input.evalSetId.value) return;
    await loadLatestRuns();
    syncPolling();
  }, { immediate: true });

  watch(hasActiveJobs, () => syncPolling());

  onBeforeUnmount(() => stopPolling());

  function runForCase(caseVersionId: string): EvalCaseRunDetail | null {
    return opencodeRunsByCase.value[caseVersionId] ?? null;
  }

  function actualOutputForCase(caseVersionId: string | null | undefined): string {
    return caseVersionId ? opencodeRunsByCase.value[caseVersionId]?.result_artifact?.content_text ?? "" : "";
  }

  function applyRunDetail(detail: EvalCaseRunDetail): void {
    opencodeRunsByCase.value = {
      ...opencodeRunsByCase.value,
      [detail.eval_case_run.case_version_id]: detail,
    };
  }

  async function loadLatestRuns(): Promise<void> {
    if (!input.skillVersionId.value || !input.evalSetId.value) return;
    try {
      const runs = await api.listEvalCaseRuns({
        skill_version_id: input.skillVersionId.value,
        eval_set_id: input.evalSetId.value,
      });
      opencodeRunsByCase.value = Object.fromEntries(runs.map((run) => [run.eval_case_run.case_version_id, run]));
    } catch (caught) {
      input.emitToast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      syncPolling();
    }
  }

  async function queueCaseRun(item: EvalSetCase): Promise<EvalCaseRunDetail> {
    const caseVersionId = item.case_version.id;
    const queued = await api.enqueueEvalCaseRun({
      skill_version_id: input.skillVersionId.value,
      eval_set_id: input.evalSetId.value,
      case_version_id: caseVersionId,
      environment_tags: ENVIRONMENT_TAGS,
      run_context: RUN_CONTEXT,
    });
    const detail = queuedRecordToDetail(queued, item);
    applyRunDetail(detail);
    startPolling();
    return detail;
  }

  async function runCase(item: EvalSetCase, options: { silent?: boolean } = {}): Promise<void> {
    const caseVersionId = item.case_version.id;
    runningCaseId.value = caseVersionId;
    try {
      await queueCaseRun(item);
      void refreshRuns();
      if (!options.silent) input.emitToast({ tone: "success", message: "Opencode 测试例已入队，状态会自动刷新。" });
    } catch (caught) {
      input.emitToast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      runningCaseId.value = null;
    }
  }

  async function runAll(): Promise<void> {
    if (busy.value || input.cases.value.length === 0) return;
    busy.value = true;
    try {
      for (const item of input.cases.value) {
        await runCase(item, { silent: true });
      }
      input.emitToast({ tone: "success", message: "Opencode 测评已全部入队，状态会自动刷新。" });
    } finally {
      busy.value = false;
      syncPolling();
    }
  }

  async function runFormalEvaluation(): Promise<string | null> {
    if (busy.value || input.cases.value.length === 0 || !input.skillVersionId.value || !input.evalSetId.value) return null;
    busy.value = true;
    try {
      const queued = [];
      for (const item of input.cases.value) {
        runningCaseId.value = item.case_version.id;
        queued.push(await queueCaseRun(item));
      }
      runningCaseId.value = null;
      input.emitToast({ tone: "success", message: "正式测评已全部入队，完成后会自动聚合。" });
      const finished = await waitForBatch(queued.map((detail) => detail.eval_case_run.id));
      const failed = finished.filter((detail) => detail.eval_case_run.status !== "succeeded");
      if (failed.length > 0) {
        input.emitToast({ tone: "danger", message: `${failed.length} 个测试例执行失败，正式测评未聚合。` });
        return null;
      }
      const recorded = await api.aggregateEvalRun({
        skill_version_id: input.skillVersionId.value,
        eval_set_id: input.evalSetId.value,
        environment_tags: ENVIRONMENT_TAGS,
        run_context: RUN_CONTEXT,
      });
      input.emitToast({ tone: "success", message: "正式测评已完成并聚合。" });
      return recorded.eval_run_id;
    } catch (caught) {
      input.emitToast({ tone: "danger", message: errorMessage(caught) });
      return null;
    } finally {
      runningCaseId.value = null;
      busy.value = false;
      syncPolling();
    }
  }

  async function retryFailed(): Promise<void> {
    if (busy.value) return;
    const failed = input.cases.value.filter((item) => runnerState(opencodeRunsByCase.value[item.case_version.id]).kind === "failed");
    if (failed.length === 0) return;
    busy.value = true;
    try {
      for (const item of failed) {
        await runCase(item, { silent: true });
      }
      input.emitToast({ tone: "success", message: "失败测试例已重新入队。" });
    } finally {
      busy.value = false;
      syncPolling();
    }
  }

  async function waitForBatch(evalCaseRunIds: string[]): Promise<EvalCaseRunDetail[]> {
    while (true) {
      const details = await Promise.all(evalCaseRunIds.map((id) => api.getEvalCaseRun(id)));
      for (const detail of details) applyRunDetail(detail);
      if (details.every((detail) => !isActiveRun(detail.eval_case_run.status))) return details;
      await delay(pollIntervalMs);
    }
  }

  function startPolling(): void {
    if (pollTimer !== null) return;
    pollTimer = window.setInterval(() => void refreshRuns(), pollIntervalMs);
  }

  function stopPolling(): void {
    if (pollTimer === null) return;
    window.clearInterval(pollTimer);
    pollTimer = null;
  }

  function syncPolling(): void {
    if (hasActiveJobs.value) {
      startPolling();
      return;
    }
    stopPolling();
  }

  async function refreshRuns(): Promise<void> {
    if (polling.value) return;
    polling.value = true;
    try {
      await loadLatestRuns();
    } finally {
      polling.value = false;
    }
  }

  return {
    board,
    busy,
    canRunFormalEvaluation,
    opencodeRunsByCase,
    pollIntervalSeconds,
    polling,
    runningCaseId,
    summary,
    actualOutputForCase,
    runAll,
    runCase,
    runFormalEvaluation,
    runForCase,
    retryFailed,
  };
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
