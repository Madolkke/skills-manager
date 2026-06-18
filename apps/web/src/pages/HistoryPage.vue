<script setup lang="ts">
import clsx from "clsx";
import { Copy, FileCheck2, GitCommitHorizontal } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { api, ApiError } from "../lib/api";
import { humanDate, scoreKind, versionName } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunDetail, EvalRunHistory, SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail; selectedRunId: string | null }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>]; toast: [toast: ToastState] }>();

const history = ref<EvalRunHistory | null>(null);
const run = ref<EvalRunDetail | null>(null);
const runs = computed(() => history.value?.runs ?? []);
const activeRunId = computed(() => resolveSelectedRunId(runs.value, props.selectedRunId));
const activeContext = computed(() => runs.value.find((item) => item.eval_run.id === activeRunId.value) ?? null);

watch(() => props.skill.skill.id, async () => {
  try {
    history.value = await api.getEvalRunHistory(props.skill.skill.id);
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
</script>

<template>
  <div class="history-layout">
    <section class="history-workspace">
      <header class="section-heading">
        <div>
          <h1>历史与证据链</h1>
          <p>每次测评记录绑定准确的 Skill 版本与当前测评集，并保存运行环境、运行结果与判定结果。</p>
        </div>
        <button class="secondary-button" type="button" @click="emit('navigate', { tab: 'evaluate', selectedRunId: null })">进入测评</button>
      </header>

      <section v-if="activeContext" class="run-evidence-panel">
        <header class="run-evidence-head">
          <div>
            <span :class="clsx('run-score', scoreKind(activeContext.eval_run))">{{ runScoreText(activeContext.eval_run.summary) }}</span>
            <h2>{{ versionName(activeContext.skill_version) }} · {{ activeContext.eval_set.name }}</h2>
            <p>{{ humanDate(activeContext.eval_run.created_at) }} · {{ activeContext.eval_run.created_by }}</p>
          </div>
        </header>
        <div class="evidence-grid">
          <span><small>Skill 版本</small><strong>{{ versionName(activeContext.skill_version) }}</strong></span>
          <span><small>测评集</small><strong>{{ activeContext.eval_set.name }}</strong></span>
          <span><small>上下文摘要</small><strong>{{ compactDigest(activeContext.eval_run.run_context_hash) }}</strong></span>
        </div>
        <div class="case-result-list">
          <article v-for="item in run?.case_results ?? []" :key="item.case_version.id" class="case-result-card">
            <header>
              <strong>{{ item.case.title }}</strong>
              <span :class="clsx('case-result-chip', item.result.passed ? 'passed' : 'failed')">{{ item.result.passed ? "通过" : "不通过" }}</span>
            </header>
            <div class="evaluation-comparison-grid">
              <section><h3>预期结果</h3><pre>{{ item.case_version.expected_output_artifact.content_text }}</pre></section>
              <section><h3>运行结果</h3><pre>{{ item.result_artifact?.content_text ?? "" }}</pre></section>
            </div>
          </article>
        </div>
      </section>
      <div v-else class="history-empty">
        <FileCheck2 :size="24" />
        <strong>还没有测评记录</strong>
        <p>先在“测评”页选择 Skill 版本与测评集版本，通过 Opencode 测评器完成测试例后聚合结果。</p>
      </div>

      <section class="version-history">
        <header class="history-section-head">
          <h2>Skill 版本链</h2>
          <p>每个 Skill 版本都是不可变快照；环境差异记录在测评记录上。</p>
        </header>
        <div class="version-group">
          <h3>{{ skill.skill.slug }}</h3>
          <div class="version-stack">
            <div v-for="version in skill.versions" :key="version.id" :class="clsx('version-row', version.id === skill.skill.current_version_id && 'current')">
              <GitCommitHorizontal :size="18" />
              <strong>{{ versionName(version) }}</strong>
              <span>{{ version.change_summary }}</span>
              <small>{{ compactDigest(version.content_digest) }}</small>
              <button class="icon-button mini" type="button" :aria-label="`复制 ${versionName(version)} 摘要`" @click="copyText('版本摘要', version.content_digest)">
                <Copy :size="14" />
              </button>
            </div>
          </div>
        </div>
      </section>
    </section>

    <aside class="run-history">
      <div class="run-history-head"><div><h2>测评记录</h2><p>{{ runs.length }} 次记录</p></div></div>
      <button
        v-for="item in runs"
        :key="item.eval_run.id"
        :class="clsx('run-row', activeRunId === item.eval_run.id && 'active')"
        type="button"
        @click="emit('navigate', { selectedRunId: item.eval_run.id })"
      >
        <span :class="clsx('run-score', scoreKind(item.eval_run))">{{ runScoreText(item.eval_run.summary) }}</span>
        <strong>{{ versionName(item.skill_version) }}</strong>
        <small>{{ item.eval_set.name }} · {{ humanDate(item.eval_run.created_at) }}</small>
      </button>
      <button v-if="runs.length === 0" class="secondary-button full-width" type="button" @click="emit('navigate', { tab: 'evaluate' })">去记录第一次测评</button>
    </aside>
  </div>
</template>
