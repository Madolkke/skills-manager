<script setup lang="ts">
import { Info } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import RunnerActionBar from "../components/RunnerActionBar.vue";
import RunnerCaseDetail from "../components/RunnerCaseDetail.vue";
import RunnerCaseQueue from "../components/RunnerCaseQueue.vue";
import RunnerStatusBoard from "../components/RunnerStatusBoard.vue";
import TagInput from "../components/TagInput.vue";
import { api, ApiError } from "../lib/api";
import { isActiveRun, queuedRecordToDetail, resolveRunnerPollInterval, runnerState, summarizeOpencodeRuns, summarizeRunnerBoard } from "../lib/evalRunner";
import { versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalCaseRunDetail, EvalSetCase, EvalSetDetail, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ refresh: []; navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();
const OPENCODE_POLL_INTERVAL_MS = resolveRunnerPollInterval(import.meta.env.VITE_OPENCODE_RUN_POLL_INTERVAL_MS);

const versions = computed(() => props.skill.versions);
const evalSet = computed(() => props.skill.summary.primary_eval_set);
const evalSetId = computed(() => evalSet.value?.id ?? "");
const skillVersionId = ref(props.skill.skill.current_version_id ?? props.skill.versions[0]?.id ?? "");
const environmentTags = ref<string[]>([]);
const detail = ref<EvalSetDetail | null>(null);
const opencodeRunsByCase = ref<Record<string, EvalCaseRunDetail>>({});
const activeCaseId = ref<string | null>(null);
const runningCaseId = ref<string | null>(null);
const busy = ref(false);
const polling = ref(false);
let opencodePollTimer: number | null = null;
const cases = computed(() => detail.value?.cases ?? []);
const active = computed(() => cases.value.find((item) => item.case_version.id === activeCaseId.value) ?? null);
const selectedVersion = computed(() => versions.value.find((version) => version.id === skillVersionId.value));
const opencodeSummary = computed(() => summarizeOpencodeRuns(cases.value, opencodeRunsByCase.value));
const canAggregateOpencode = computed(() => !busy.value && cases.value.length > 0 && opencodeSummary.value.failedRuns === 0 && opencodeSummary.value.pending === 0);
const hasActiveOpencodeJobs = computed(() => Object.values(opencodeRunsByCase.value).some((run) => isActiveRun(run.eval_case_run.status)));
const activeRun = computed(() => (active.value ? opencodeRunsByCase.value[active.value.case_version.id] ?? null : null));
const activeRunState = computed(() => runnerState(activeRun.value));
const activeActualOutput = computed(() => activeRun.value?.result_artifact?.content_text ?? "");
const opencodeBoard = computed(() => summarizeRunnerBoard(cases.value, opencodeRunsByCase.value));
const pollIntervalSeconds = computed(() => Math.round(OPENCODE_POLL_INTERVAL_MS / 1000));

watch(evalSetId, async (id) => {
  if (!id) {
    detail.value = null;
    activeCaseId.value = null;
    return;
  }
  try {
    const next = await api.getEvalSet(id);
    detail.value = next;
    activeCaseId.value = null;
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}, { immediate: true });

watch(() => skillVersionId.value, () => {
  activeCaseId.value = null;
});

watch([skillVersionId, evalSetId, detail], async () => {
  if (!skillVersionId.value || !evalSetId.value || !detail.value) return;
  await loadLatestOpencodeRuns();
  syncOpencodePolling();
}, { immediate: true });

watch(hasActiveOpencodeJobs, () => syncOpencodePolling());

onMounted(() => window.addEventListener("keydown", onKeyDown));
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeyDown);
  stopOpencodePolling();
});

async function copyText(label: string, text?: string | null): Promise<void> {
  const content = text ?? "";
  if (!content.trim()) return;
  try {
    await navigator.clipboard.writeText(content);
    emit("toast", { tone: "success", message: `${label} 已复制。` });
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}

async function aggregateOpencodeRun(): Promise<void> {
  if (!canAggregateOpencode.value) return;
  busy.value = true;
  try {
    const recorded = await api.aggregateEvalRun({
      skill_version_id: skillVersionId.value,
      eval_set_id: evalSetId.value,
      environment_tags: environmentTags.value,
      run_context: {},
    });
    emit("toast", { tone: "success", message: "Opencode 测评已聚合。" });
    emit("refresh");
    emit("navigate", { tab: "history", selectedRunId: recorded.eval_run_id });
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  } finally {
    busy.value = false;
  }
}

async function runActiveCase(): Promise<void> {
  if (!active.value) return;
  await runOpencodeCase(active.value);
}

async function runAllOpencodeCases(): Promise<void> {
  if (busy.value || cases.value.length === 0) return;
  busy.value = true;
  try {
    for (const item of cases.value) {
      await runOpencodeCase(item, { silent: true });
    }
    emit("toast", { tone: "success", message: "Opencode 测评已全部入队，状态会自动刷新。" });
  } finally {
    busy.value = false;
    syncOpencodePolling();
  }
}

async function loadLatestOpencodeRuns(): Promise<void> {
  if (!skillVersionId.value || !evalSetId.value) return;
  try {
    const runs = await api.listEvalCaseRuns({
      skill_version_id: skillVersionId.value,
      eval_set_id: evalSetId.value,
    });
    opencodeRunsByCase.value = Object.fromEntries(runs.map((run) => [run.eval_case_run.case_version_id, run]));
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  } finally {
    syncOpencodePolling();
  }
}

async function runOpencodeCase(item: EvalSetCase, options: { silent?: boolean } = {}): Promise<void> {
  const caseVersionId = item.case_version.id;
  runningCaseId.value = caseVersionId;
  try {
    const queued = await api.enqueueEvalCaseRun({
      skill_version_id: skillVersionId.value,
      eval_set_id: evalSetId.value,
      case_version_id: caseVersionId,
      environment_tags: environmentTags.value,
      run_context: {},
    });
    opencodeRunsByCase.value = {
      ...opencodeRunsByCase.value,
      [caseVersionId]: queuedRecordToDetail(queued, item),
    };
    startOpencodePolling();
    void refreshOpencodeRuns();
    if (!options.silent) emit("toast", { tone: "success", message: "Opencode 测试例已入队，状态会自动刷新。" });
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  } finally {
    runningCaseId.value = null;
  }
}

async function retryFailedOpencodeCases(): Promise<void> {
  if (busy.value) return;
  const failed = cases.value.filter((item) => runnerState(opencodeRunsByCase.value[item.case_version.id]).kind === "failed");
  if (failed.length === 0) return;
  busy.value = true;
  try {
    for (const item of failed) {
      await runOpencodeCase(item, { silent: true });
    }
    emit("toast", { tone: "success", message: "失败测试例已重新入队。" });
  } finally {
    busy.value = false;
    syncOpencodePolling();
  }
}

function startOpencodePolling(): void {
  if (opencodePollTimer !== null) return;
  opencodePollTimer = window.setInterval(() => void refreshOpencodeRuns(), OPENCODE_POLL_INTERVAL_MS);
}

function stopOpencodePolling(): void {
  if (opencodePollTimer === null) return;
  window.clearInterval(opencodePollTimer);
  opencodePollTimer = null;
}

function syncOpencodePolling(): void {
  if (hasActiveOpencodeJobs.value) {
    startOpencodePolling();
    return;
  }
  stopOpencodePolling();
}

async function refreshOpencodeRuns(): Promise<void> {
  if (polling.value) return;
  polling.value = true;
  try {
    await loadLatestOpencodeRuns();
  } finally {
    polling.value = false;
  }
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
  const key = event.key.toLowerCase();
  if (/^[1-9]$/.test(key)) {
    const target = cases.value[Number(key) - 1];
    if (target) {
      event.preventDefault();
      activeCaseId.value = target.case_version.id;
    }
  }
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}

</script>

<template>
  <div class="evaluate-page">
    <section class="evaluation-selectors">
      <div class="evaluation-selector-card">
        <label class="field-label">
          <span>Skill 版本</span>
          <select v-model="skillVersionId">
            <option v-for="version in versions" :key="version.id" :value="version.id">{{ versionName(version) }}</option>
          </select>
        </label>
        <p>{{ selectedVersion?.change_summary ?? "无版本说明。" }}</p>
      </div>
      <div class="evaluation-selector-card">
        <span>当前测评集</span>
        <strong>{{ evalSet?.name ?? "未绑定" }}</strong>
        <small>{{ cases.length }} 个测试例</small>
      </div>
      <div class="evaluation-selector-card">
        <span>运行环境标签</span>
        <TagInput :value="environmentTags" :suggestions="['local', 'opencode', 'windows', 'macos', 'linux']" @change="environmentTags = $event" />
        <small class="selector-helper">{{ polling ? "正在刷新任务状态" : `每 ${pollIntervalSeconds} 秒轮询一次` }}</small>
      </div>
      <div class="info-box">
        <Info :size="18" />
        <div>
          <strong>通过 Opencode 容器执行测评</strong>
          <p>页面会恢复上一次任务结果，并显示队列、后台进程、会话、工作目录与错误信息。</p>
        </div>
      </div>
    </section>

    <section class="eval-progress-panel runner-progress-panel">
      <div class="progress-summary-card">
        <div class="progress-ring" :style="{ '--coverage': `${opencodeSummary.coverage}%` }">
          <span>{{ opencodeSummary.coverage }}%</span>
        </div>
        <div class="progress-copy">
          <span>进度</span>
          <h1>{{ opencodeSummary.confirmed }}/{{ cases.length }}</h1>
          <p>{{ opencodeSummary.pending }} 个测试例尚未完成，{{ opencodeSummary.failedRuns }} 个执行失败。</p>
        </div>
      </div>
      <div class="progress-metrics">
        <div class="progress-metric passed"><i /><strong>{{ opencodeSummary.passed }}</strong><small>通过</small></div>
        <div class="progress-metric failed"><i /><strong>{{ opencodeSummary.failed }}</strong><small>不通过</small></div>
        <div class="progress-metric pending"><i /><strong>{{ opencodeSummary.pending }}</strong><small>待评估</small></div>
      </div>
      <RunnerStatusBoard :items="opencodeBoard" />
    </section>

    <div class="manual-eval-grid">
      <RunnerCaseQueue
        :active-case-id="active?.case_version.id ?? null"
        :cases="cases"
        :pending="opencodeSummary.pending"
        :runs-by-case="opencodeRunsByCase"
        @select="activeCaseId = $event"
      />
      <RunnerCaseDetail
        :active="active"
        :actual-output="activeActualOutput"
        :poll-interval-seconds="pollIntervalSeconds"
        :polling="polling"
        :run="activeRun"
        :running-case-id="runningCaseId"
        :state="activeRunState"
        @copy="copyText"
        @run="runActiveCase"
      />
    </div>

    <RunnerActionBar
      :busy="busy"
      :can-aggregate="canAggregateOpencode"
      :case-count="cases.length"
      :poll-interval-seconds="pollIntervalSeconds"
      :summary="opencodeSummary"
      @aggregate="aggregateOpencodeRun"
      @retry-failed="retryFailedOpencodeCases"
      @run-all="runAllOpencodeCases"
    />
  </div>
</template>
