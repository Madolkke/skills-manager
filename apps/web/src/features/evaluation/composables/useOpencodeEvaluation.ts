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
  environmentTags: { value: string[] };
  ready: ComputedRef<boolean>;
  emitToast: (toast: ToastState) => void;
};

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
  const canAggregate = computed(() => !busy.value && input.cases.value.length > 0 && summary.value.failedRuns === 0 && summary.value.pending === 0);
  const hasActiveJobs = computed(() => Object.values(opencodeRunsByCase.value).some((run) => isActiveRun(run.eval_case_run.status)));

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

  async function runCase(item: EvalSetCase, options: { silent?: boolean } = {}): Promise<void> {
    const caseVersionId = item.case_version.id;
    runningCaseId.value = caseVersionId;
    try {
      const queued = await api.enqueueEvalCaseRun({
        skill_version_id: input.skillVersionId.value,
        eval_set_id: input.evalSetId.value,
        case_version_id: caseVersionId,
        environment_tags: input.environmentTags.value,
        run_context: {},
      });
      opencodeRunsByCase.value = {
        ...opencodeRunsByCase.value,
        [caseVersionId]: queuedRecordToDetail(queued, item),
      };
      startPolling();
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

  async function aggregate(): Promise<string | null> {
    if (!canAggregate.value) return null;
    busy.value = true;
    try {
      const recorded = await api.aggregateEvalRun({
        skill_version_id: input.skillVersionId.value,
        eval_set_id: input.evalSetId.value,
        environment_tags: input.environmentTags.value,
        run_context: {},
      });
      input.emitToast({ tone: "success", message: "Opencode 测评已聚合。" });
      return recorded.eval_run_id;
    } catch (caught) {
      input.emitToast({ tone: "danger", message: errorMessage(caught) });
      return null;
    } finally {
      busy.value = false;
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
    canAggregate,
    opencodeRunsByCase,
    pollIntervalSeconds,
    polling,
    runningCaseId,
    summary,
    actualOutputForCase,
    aggregate,
    runAll,
    runCase,
    runForCase,
    retryFailed,
  };
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
