<script setup lang="ts">
import clsx from "clsx";
import { Info, Play, Save } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import TagInput from "../components/TagInput.vue";
import { api, ApiError } from "../lib/api";
import { manualRecordHint, manualResultLabel, nextPendingCaseVersionId, runCaseEvaluation, summarizeManualEval, type ManualCaseResult } from "../lib/eval";
import { versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalSetDetail, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ refresh: []; navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();

const versions = computed(() => props.skill.versions);
const evalSet = computed(() => props.skill.summary.primary_eval_set);
const evalSetId = computed(() => evalSet.value?.id ?? "");
const skillVersionId = ref(props.skill.skill.current_version_id ?? props.skill.versions[0]?.id ?? "");
const environmentTags = ref<string[]>([]);
const detail = ref<EvalSetDetail | null>(null);
const resultsByVersion = ref<Record<string, Record<string, ManualCaseResult>>>({});
const caseRunsByContext = ref<Record<string, string>>({});
const activeCaseId = ref<string | null>(null);
const runningCaseId = ref<string | null>(null);
const busy = ref(false);
const cases = computed(() => detail.value?.cases ?? []);
const currentResults = computed(() => resultsByVersion.value[skillVersionId.value] ?? {});
const summary = computed(() => summarizeManualEval(cases.value.length, currentResults.value));
const active = computed(() => cases.value.find((item) => item.case_version.id === activeCaseId.value) ?? cases.value[0] ?? null);
const selectedVersion = computed(() => versions.value.find((version) => version.id === skillVersionId.value));
const canRecord = computed(() => !busy.value && Boolean(skillVersionId.value && evalSetId.value) && summary.value.pending === 0 && cases.value.length > 0);

watch(evalSetId, async (id) => {
  if (!id) {
    detail.value = null;
    activeCaseId.value = null;
    return;
  }
  try {
    const next = await api.getEvalSet(id);
    detail.value = next;
    activeCaseId.value = next.cases[0]?.case_version.id ?? null;
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}, { immediate: true });

watch(() => skillVersionId.value, () => {
  activeCaseId.value = cases.value[0]?.case_version.id ?? null;
});

onMounted(() => window.addEventListener("keydown", onKeyDown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeyDown));

function mark(caseVersionId: string, passed: boolean): void {
  updateCurrentResults(caseVersionId, { actualOutput: currentResults.value[caseVersionId]?.actualOutput ?? "", passed });
}

function updateActualOutput(caseVersionId: string, actualOutput: string): void {
  updateCurrentResults(caseVersionId, { actualOutput, passed: currentResults.value[caseVersionId]?.passed });
}

function goNext(): void {
  const nextId = nextPendingCaseVersionId(cases.value, currentResults.value, activeCaseId.value);
  if (nextId) activeCaseId.value = nextId;
}

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

async function recordRun(): Promise<void> {
  if (!canRecord.value) return;
  busy.value = true;
  try {
    for (const item of cases.value) {
      const caseVersionId = item.case_version.id;
      const result = currentResults.value[caseVersionId];
      if (result?.passed === undefined) continue;
      await ensureCaseRunRecorded(caseVersionId, result);
    }
    const recorded = await api.aggregateEvalRun({
      skill_version_id: skillVersionId.value,
      eval_set_id: evalSetId.value,
      strategy: "manual_pass_fail",
      environment_tags: environmentTags.value,
      run_context: {},
    });
    emit("toast", { tone: "success", message: "测评结果已记录。" });
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
  const caseVersionId = active.value.case_version.id;
  runningCaseId.value = caseVersionId;
  try {
    const queued = await api.enqueueEvalCaseRun({
      skill_version_id: skillVersionId.value,
      eval_set_id: evalSetId.value,
      case_version_id: caseVersionId,
      strategy: "manual_pass_fail",
      environment_tags: environmentTags.value,
      run_context: {},
    });
    const evaluated = await runCaseEvaluation({
      skillVersionId: skillVersionId.value,
      evalSetId: evalSetId.value,
      caseItem: active.value,
    });
    if (evaluated) {
      updateCurrentResults(caseVersionId, evaluated);
      await api.completeEvalCaseRun(queued.eval_case_run_id, { passed: evaluated.passed === true, actual_output: evaluated.actualOutput });
      rememberCaseRun(caseRunCacheKey(caseVersionId), queued.eval_case_run_id);
      emit("toast", { tone: "success", message: "单个 case 已运行并写入结果。" });
    } else {
      emit("toast", { tone: "info", message: "单个 case 的运行入口已预留，实际测评逻辑待接入。" });
    }
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  } finally {
    runningCaseId.value = null;
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
  if (key === "p" && active.value) mark(active.value.case_version.id, true);
  if (key === "f" && active.value) mark(active.value.case_version.id, false);
  if (key === "n" && summary.value.pending > 0) goNext();
  if (key === "s" && canRecord.value) void recordRun();
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
}

function manualStatusClass(value?: boolean): string {
  if (value === true) return "passed";
  if (value === false) return "failed";
  return "pending";
}

function updateCurrentResults(caseVersionId: string, nextResult: ManualCaseResult): void {
  const versionId = skillVersionId.value;
  const existing = resultsByVersion.value[versionId] ?? {};
  resultsByVersion.value = {
    ...resultsByVersion.value,
    [versionId]: {
      ...existing,
      [caseVersionId]: nextResult,
    },
  };
}

async function ensureCaseRunRecorded(caseVersionId: string, result: ManualCaseResult): Promise<void> {
  const cacheKey = caseRunCacheKey(caseVersionId);
  const existingRunId = caseRunsByContext.value[cacheKey];
  if (existingRunId) {
    return;
  }
  const queued = await api.enqueueEvalCaseRun({
    skill_version_id: skillVersionId.value,
    eval_set_id: evalSetId.value,
    case_version_id: caseVersionId,
    strategy: "manual_pass_fail",
    environment_tags: environmentTags.value,
    run_context: {},
  });
  await api.completeEvalCaseRun(queued.eval_case_run_id, { passed: result.passed === true, actual_output: result.actualOutput });
  rememberCaseRun(cacheKey, queued.eval_case_run_id);
}

function rememberCaseRun(cacheKey: string, evalCaseRunId: string): void {
  caseRunsByContext.value = { ...caseRunsByContext.value, [cacheKey]: evalCaseRunId };
}

function caseRunCacheKey(caseVersionId: string): string {
  return JSON.stringify({
    skillVersionId: skillVersionId.value,
    evalSetId: evalSetId.value,
    caseVersionId,
    strategy: "manual_pass_fail",
    environmentTags: [...environmentTags.value].sort(),
    runContext: {},
  });
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
          <span>SkillVersion</span>
          <select v-model="skillVersionId">
            <option v-for="version in versions" :key="version.id" :value="version.id">{{ versionName(version) }}</option>
          </select>
        </label>
        <p>{{ selectedVersion?.change_summary ?? "无版本说明。" }}</p>
      </div>
      <div class="evaluation-selector-card">
        <span>当前测评集</span>
        <strong>{{ evalSet?.name ?? "未绑定" }}</strong>
        <small>{{ cases.length }} cases</small>
      </div>
      <div class="evaluation-selector-card">
        <span>运行环境标签</span>
        <TagInput :value="environmentTags" :suggestions="['local', 'manual', 'windows', 'macos', 'linux']" @change="environmentTags = $event" />
      </div>
      <div class="info-box">
        <Info :size="18" />
        <div>
          <strong>在此页面执行人工测评</strong>
          <p>选择 SkillVersion，使用当前测评集逐条输入本次运行结果并记录环境上下文。</p>
        </div>
      </div>
    </section>

    <section class="eval-progress-panel">
      <div class="progress-summary-card">
        <div class="progress-ring" :style="{ '--coverage': `${summary.coverage}%` }">
          <span>{{ summary.coverage }}%</span>
        </div>
        <div class="progress-copy">
          <span>进度</span>
          <h1>{{ summary.confirmed }}/{{ cases.length }}</h1>
          <p>{{ manualRecordHint(cases.length, summary.pending) }}</p>
        </div>
      </div>
      <div class="progress-metrics">
        <div class="progress-metric passed"><i /><strong>{{ summary.passed }}</strong><small>通过</small></div>
        <div class="progress-metric failed"><i /><strong>{{ summary.failed }}</strong><small>不通过</small></div>
        <div class="progress-metric pending"><i /><strong>{{ summary.pending }}</strong><small>待评估</small></div>
      </div>
    </section>

    <div class="manual-eval-grid">
      <aside class="manual-case-list">
        <header class="manual-list-head">
          <div>
            <h2>Case 列表</h2>
            <p>{{ summary.pending }} 个待评估</p>
          </div>
          <span>{{ cases.length }}</span>
        </header>
        <button
          v-for="(item, index) in cases"
          :key="item.case_version.id"
          :class="clsx('manual-case-row', active?.case_version.id === item.case_version.id && 'active')"
          type="button"
          @click="activeCaseId = item.case_version.id"
        >
          <span :class="clsx('manual-status-dot', manualStatusClass(currentResults[item.case_version.id]?.passed))" aria-hidden="true" />
          <span class="manual-case-index">#{{ item.position + 1 }}</span>
          <span class="manual-case-copy">
            <strong>{{ item.case.title }}</strong>
            <small><span>case v{{ item.case_version.version_number }}</span><span>{{ manualResultLabel(currentResults[item.case_version.id]?.passed) }}</span></small>
          </span>
          <kbd v-if="index < 9" class="manual-shortcut-chip">{{ index + 1 }}</kbd>
        </button>
      </aside>

      <section class="manual-case-detail">
        <template v-if="active">
          <header class="manual-case-head">
            <div>
              <span>Case #{{ active.position + 1 }}</span>
              <h2>{{ active.case.title }}</h2>
            </div>
            <div class="button-row">
              <button class="secondary-button" type="button" :disabled="runningCaseId === active.case_version.id" @click="runActiveCase">
                <Play :size="16" />
                {{ runningCaseId === active.case_version.id ? "运行中..." : "运行此 case" }}
              </button>
              <button class="secondary-button" type="button" @click="copyText('input', active.case_version.input_artifact.content_text)">复制 input</button>
              <button class="secondary-button" type="button" @click="copyText('expected output', active.case_version.expected_output_artifact.content_text)">复制 expected</button>
            </div>
          </header>
          <div class="manual-comparison-grid">
            <section><h3>Input</h3><pre>{{ active.case_version.input_artifact.content_text }}</pre></section>
            <section><h3>Expected output</h3><pre>{{ active.case_version.expected_output_artifact.content_text }}</pre></section>
          </div>
          <label class="field-label">
            <span>Actual output</span>
            <textarea
              :value="currentResults[active.case_version.id]?.actualOutput ?? ''"
              @input="updateActualOutput(active.case_version.id, ($event.target as HTMLTextAreaElement).value)"
            />
          </label>
          <div class="manual-case-actions">
            <button class="success-button" type="button" @click="mark(active.case_version.id, true)">通过</button>
            <button class="danger-button" type="button" @click="mark(active.case_version.id, false)">不通过</button>
            <button class="secondary-button" type="button" :disabled="summary.pending === 0" @click="goNext">下一个待评估</button>
          </div>
        </template>
        <div v-else class="quiet-panel">没有可测评的 case。</div>
      </section>
    </div>

    <div class="manual-eval-action-bar">
      <span>{{ manualRecordHint(cases.length, summary.pending) }}</span>
      <button class="primary-button" type="button" :disabled="!canRecord" @click="recordRun">
        <Save :size="17" />
        {{ busy ? "记录中..." : "记录测评" }}
      </button>
    </div>
  </div>
</template>
