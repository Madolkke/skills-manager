<script setup lang="ts">
import clsx from "clsx";
import { FileCheck2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import HistoryCaseResultCard from "../features/evaluation/components/HistoryCaseResultCard.vue";
import { api, ApiError } from "../lib/api";
import { humanDate, scoreKind, versionName } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunDetail, EvalRunHistory, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail; selectedRunId: string | null; selectedEvalSetId: string | null }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();

const history = ref<EvalRunHistory | null>(null);
const run = ref<EvalRunDetail | null>(null);
const evalSets = computed(() => props.skill.eval_sets);
const fallbackEvalSetId = computed(() => props.skill.summary.primary_eval_set?.id ?? evalSets.value[0]?.id ?? "");
const evalSetId = computed(() => {
  const requested = props.selectedEvalSetId;
  return evalSets.value.some((item) => item.id === requested) ? requested ?? "" : fallbackEvalSetId.value;
});
const evalSetOptions = computed(() => evalSets.value.map((item) => ({ value: item.id, label: item.name, description: item.description || "暂无描述" })));
const runs = computed(() => history.value?.runs ?? []);
const activeRunId = computed(() => resolveSelectedRunId(runs.value, props.selectedRunId));
const activeContext = computed(() => runs.value.find((item) => item.eval_run.id === activeRunId.value) ?? null);

watch([() => props.skill.skill.id, evalSetId], async ([skillId, currentEvalSetId]) => {
  if (currentEvalSetId && currentEvalSetId !== props.selectedEvalSetId) emit("navigate", { selectedEvalSetId: currentEvalSetId, selectedRunId: null });
  try {
    history.value = await api.getEvalRunHistory(skillId, currentEvalSetId);
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
    history.value = { skill: props.skill.skill, runs: [] };
  }
}, { immediate: true });

watch(activeRunId, async (id) => {
  if (!id) {
    run.value = null;
    return;
  }
  try {
    run.value = await api.getEvalRun(id);
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
    run.value = null;
  }
}, { immediate: true });

async function copyText(label: string, value?: string | null): Promise<void> {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    emit("toast", { tone: "success", message: `${label} 已复制。` });
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}

function selectEvalSet(id: string): void {
  emit("navigate", { selectedEvalSetId: id, selectedRunId: null });
}
</script>

<template>
  <div class="history-layout">
    <section class="history-workspace">
      <header class="section-heading">
        <div class="history-heading-actions">
          <label class="history-evalset-filter">
            <span>选择测评集</span>
            <DropdownSelect :model-value="evalSetId" :options="evalSetOptions" aria-label="按测评集筛选历史" @update:model-value="selectEvalSet" />
          </label>
        </div>
      </header>

      <section v-if="activeContext" class="run-evidence-panel">
        <header class="run-evidence-head">
          <div>
            <span :class="clsx('run-score', scoreKind(activeContext.eval_run))">{{ runScoreText(activeContext.eval_run.summary) }}</span>
            <h2>{{ versionName(activeContext.skill_version) }} · {{ activeContext.eval_set.name }}</h2>
            <p>{{ humanDate(activeContext.eval_run.created_at) }} · {{ activeContext.eval_run.created_by }}</p>
          </div>
        </header>
        <div class="run-evidence-body">
          <div class="evidence-grid">
            <span><small>Skill 版本</small><strong>{{ versionName(activeContext.skill_version) }}</strong></span>
            <span><small>测评集</small><strong>{{ activeContext.eval_set.name }}</strong></span>
            <span><small>上下文摘要</small><strong>{{ compactDigest(activeContext.eval_run.run_context_hash) }}</strong></span>
          </div>
          <div class="case-result-list">
            <HistoryCaseResultCard v-for="item in run?.case_results ?? []" :key="item.case_version.id" :item="item" @copy="copyText" />
            <div v-if="run && run.case_results.length === 0" class="history-empty inline">
              <FileCheck2 :size="22" />
              <strong>这次聚合没有测试例结果</strong>
              <p>请回到“测评”页确认当前测评集中的测试例已经完成运行。</p>
            </div>
          </div>
        </div>
      </section>
      <div v-else class="history-empty">
        <FileCheck2 :size="24" />
        <strong>还没有测评记录</strong>
        <p>先在“测评”页选择 Skill 版本与测评集版本，通过 Opencode 测评器完成测试例后聚合结果。</p>
      </div>
    </section>

    <aside class="run-history">
      <div class="run-history-head"><div><h2>测评记录</h2><p>{{ runs.length }} 次记录</p></div></div>
      <button
        v-for="(item, index) in runs"
        :key="item.eval_run.id"
        :class="clsx('run-row', activeRunId === item.eval_run.id && 'active')"
        type="button"
        @click="emit('navigate', { selectedRunId: item.eval_run.id })"
      >
        <span class="run-row-tags">
          <span class="run-row-count">第 {{ runs.length - index }} 次</span>
          <span v-if="index === 0" class="run-latest-chip">最新</span>
          <span :class="clsx('run-score', scoreKind(item.eval_run))">{{ runScoreText(item.eval_run.summary) }}</span>
        </span>
        <strong>{{ versionName(item.skill_version) }}</strong>
        <small>{{ item.eval_set.name }} · {{ humanDate(item.eval_run.created_at) }}</small>
      </button>
      <button v-if="runs.length === 0" class="secondary-button full-width" type="button" @click="emit('navigate', { tab: 'evaluate', selectedEvalSetId: evalSetId })">去记录第一次测评</button>
    </aside>
  </div>
</template>
