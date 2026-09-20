<script setup lang="ts">
import type { SkillCore } from "../lib/api/paginationApi";

import clsx from "clsx";
import { FileCheck2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import PaginationBar from "../components/PaginationBar.vue";
import { usePagedQuery } from "../composables/usePagedQuery";
import { paginationApi } from "../lib/api/paginationApi";
import DropdownSelect from "../components/DropdownSelect.vue";
import HistoryCaseResultCard from "../features/evaluation/components/HistoryCaseResultCard.vue";
import { api, ApiError } from "../lib/api";
import { humanDate, scoreKind, versionName } from "../lib/format";
import { compactDigest, runScoreText } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillCore; selectedRunId: string | null; selectedEvalSetId: string | null }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();


const run = ref<EvalRunDetail | null>(null);
const detailLoading = ref(false);
const detailError = ref("");
const detailRetry = ref(0);
const evalSets = computed(() => props.skill.eval_sets);
const fallbackEvalSetId = computed(() => props.skill.summary.primary_eval_set?.id ?? evalSets.value[0]?.id ?? "");
const evalSetId = computed(() => {
  const requested = props.selectedEvalSetId;
  return evalSets.value.some((item) => item.id === requested) ? requested ?? "" : fallbackEvalSetId.value;
});
const evalSetOptions = computed(() => evalSets.value.map((item) => ({ value: item.id, label: item.name, description: item.description || "暂无描述" })));
const { page, pageSize, items: runs, total, loading, error, reload } = usePagedQuery("runs",
  () => ({ eval_set_id: evalSetId.value, skill: props.skill.skill.id }),
  (params, signal) => paginationApi.runs(props.skill.skill.id, { page: params.page, page_size: params.page_size, eval_set_id: params.eval_set_id }, signal));
const activeRunId = computed(() => props.selectedRunId ?? runs.value.find(item => item.eval_run.eval_set_id === evalSetId.value)?.eval_run.id ?? null);
const activeContext = computed(() => run.value);
watch([activeRunId, detailRetry, evalSetId], async ([id], _, cleanup) => {
  let expired = false; cleanup(() => { expired = true; }); run.value = null;
  detailError.value = ""; detailLoading.value = Boolean(id);
  if (!id) return;
  try { const detail = await api.getEvalRun(id); if (!expired) run.value = detail; }
  catch (caught) { if (!expired) detailError.value = errorMessage(caught); }
  finally { if (!expired) detailLoading.value = false; }
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
  page.value = 1;
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
      <div v-else-if="detailLoading || loading" class="history-empty" aria-live="polite">正在加载测评记录…</div>
      <div v-else-if="detailError" class="history-empty" role="alert">
        <p>{{ detailError }}</p><button class="secondary-button" type="button" @click="detailRetry++">重试详情</button>
      </div>
      <div v-else-if="!error" class="history-empty">
        <FileCheck2 :size="24" />
        <strong>还没有测评记录</strong>
        <p>先在“测评”页选择 Skill 版本与测评集版本，通过 Opencode 测评器完成测试例后聚合结果。</p>
      </div>
    </section>

    <aside class="run-history">
      <div class="run-history-head"><div><h2>测评记录</h2><p>{{ total }} 次记录</p></div></div>
      <button
        v-for="(item, index) in runs"
        :key="item.eval_run.id"
        :class="clsx('run-row', activeRunId === item.eval_run.id && 'active')"
        type="button"
        @click="emit('navigate', { selectedRunId: item.eval_run.id })"
      >
        <span class="run-row-tags">
          <span class="run-row-count">第 {{ total - (page - 1) * pageSize - index }} 次</span>
          <span v-if="page === 1 && index === 0" class="run-latest-chip">最新</span>
          <span :class="clsx('run-score', scoreKind(item.eval_run))">{{ runScoreText(item.eval_run.summary) }}</span>
        </span>
        <strong>{{ versionName(item.skill_version) }}</strong>
        <small>{{ item.eval_set.name }} · {{ humanDate(item.eval_run.created_at) }}</small>
      </button>
      <button v-if="!loading && !error && runs.length === 0" class="secondary-button full-width" type="button" @click="emit('navigate', { tab: 'evaluate', selectedEvalSetId: evalSetId })">去记录第一次测评</button>
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" :loading="loading" :error="error" @retry="reload" />
    </aside>
  </div>
</template>
