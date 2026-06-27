<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import RunnerActionBar from "../features/evaluation/components/RunnerActionBar.vue";
import RunnerCaseDetail from "../features/evaluation/components/RunnerCaseDetail.vue";
import RunnerCaseQueue from "../features/evaluation/components/RunnerCaseQueue.vue";
import RunnerStatusBoard from "../features/evaluation/components/RunnerStatusBoard.vue";
import { useOpencodeEvaluation } from "../features/evaluation/composables/useOpencodeEvaluation";
import { api, ApiError } from "../lib/api";
import { runnerState } from "../features/evaluation/lib/evalRunner";
import { versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalSetDetail, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail; selectedEvalSetId: string | null }>();
const emit = defineEmits<{ refresh: []; navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();

const versions = computed(() => props.skill.versions);
const evalSets = computed(() => props.skill.eval_sets);
const fallbackEvalSetId = computed(() => props.skill.summary.primary_eval_set?.id ?? evalSets.value[0]?.id ?? "");
const evalSetId = computed(() => {
  const requested = props.selectedEvalSetId;
  return evalSets.value.some((item) => item.id === requested) ? requested ?? "" : fallbackEvalSetId.value;
});
const skillVersionId = ref(props.skill.skill.current_version_id ?? props.skill.versions[0]?.id ?? "");
const detail = ref<EvalSetDetail | null>(null);
const activeCaseId = ref<string | null>(null);
const cases = computed(() => detail.value?.cases ?? []);
const active = computed(() => cases.value.find((item) => item.case_version.id === activeCaseId.value) ?? null);
const selectedVersion = computed(() => versions.value.find((version) => version.id === skillVersionId.value));
const selectedVersionSummary = computed(() => cleanVersionSummary(selectedVersion.value?.change_summary));
const versionOptions = computed(() => versions.value.map((version) => ({ value: version.id, label: versionName(version) })));
const evalSetOptions = computed(() => evalSets.value.map((item) => ({ value: item.id, label: item.name, description: `${item.description || "暂无描述"} · ${item.id === fallbackEvalSetId.value ? "默认" : "自定义"}` })));
const evalSetLoaded = computed(() => Boolean(detail.value));
const canRunEvaluation = computed(() => Boolean(props.skill.capabilities?.permissions["eval.run"]));
const {
  board: opencodeBoard,
  busy,
  canRunFormalEvaluation,
  opencodeRunsByCase,
  pollIntervalSeconds,
  polling,
  runningCaseId,
  summary: opencodeSummary,
  actualOutputForCase,
  runAll,
  runCase,
  runFormalEvaluation,
  runForCase,
  retryFailed,
} = useOpencodeEvaluation({
  cases,
  skillVersionId,
  evalSetId,
  ready: evalSetLoaded,
  emitToast: (toast) => emit("toast", toast),
});
const activeRun = computed(() => (active.value ? runForCase(active.value.case_version.id) : null));
const activeRunState = computed(() => runnerState(activeRun.value));
const activeActualOutput = computed(() => actualOutputForCase(active.value?.case_version.id));

watch(evalSetId, async (id) => {
  if (!id) {
    detail.value = null;
    activeCaseId.value = null;
    return;
  }
  if (id !== props.selectedEvalSetId) emit("navigate", { selectedEvalSetId: id, selectedRunId: null });
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

onMounted(() => window.addEventListener("keydown", onKeyDown));
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeyDown);
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

async function runFormalOpencodeEvaluation(): Promise<void> {
  if (!canRunEvaluation.value) {
    emit("toast", { tone: "danger", message: "当前身份没有运行测评权限。" });
    return;
  }
  const evalRunId = await runFormalEvaluation();
  if (!evalRunId) return;
  emit("refresh");
  emit("navigate", { tab: "history", selectedEvalSetId: evalSetId.value, selectedRunId: evalRunId });
}

async function runActiveCase(): Promise<void> {
  if (!active.value) return;
  if (!canRunEvaluation.value) {
    emit("toast", { tone: "danger", message: "当前身份没有运行测评权限。" });
    return;
  }
  await runCase(active.value);
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

function selectEvalSet(id: string): void {
  emit("navigate", { selectedEvalSetId: id, selectedRunId: null });
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}

function cleanVersionSummary(value?: string | null): string {
  const text = value?.trim() ?? "";
  if (!text || text.startsWith("Imported standard skill bundle with")) return "";
  return text;
}

</script>

<template>
  <div class="evaluate-page">
    <section class="evaluation-selectors">
      <div class="evaluation-selector-card">
        <label class="field-label">
          <span>Skill 版本</span>
          <DropdownSelect v-model="skillVersionId" :options="versionOptions" aria-label="选择 Skill 版本" />
        </label>
        <p v-if="selectedVersionSummary">{{ selectedVersionSummary }}</p>
      </div>
      <div class="evaluation-selector-card">
        <label class="field-label">
          <span>当前测评集</span>
          <DropdownSelect :model-value="evalSetId" :options="evalSetOptions" aria-label="选择测评集" @update:model-value="selectEvalSet" />
        </label>
      </div>
      <RunnerActionBar
        :busy="busy"
        :can-run-formal="canRunFormalEvaluation && canRunEvaluation"
        :case-count="cases.length"
        :disabled="!canRunEvaluation"
        :poll-interval-seconds="pollIntervalSeconds"
        :summary="opencodeSummary"
        @retry-failed="retryFailed"
        @run-all="runAll"
        @run-formal="runFormalOpencodeEvaluation"
      />
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

    <div class="evaluation-runner-grid">
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
      <p v-if="!canRunEvaluation" class="field-help permission-hint">当前身份没有运行测评权限，需要 evaluator、maintainer、owner 或 admin 角色。</p>
    </div>
  </div>
</template>
