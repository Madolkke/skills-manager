<script setup lang="ts">
import clsx from "clsx";
import { computed } from "vue";
import RunnerStatusChip from "./RunnerStatusChip.vue";
import { modelLabel, promptSourceLabel, runActivityHint, runnerState, runTimeLabel, type RunnerState } from "../lib/evalRunner";
import type { EvalCaseRunDetail, EvalSetCase } from "../types";

const props = defineProps<{
  activeCaseId: string | null;
  cases: EvalSetCase[];
  pending: number;
  runsByCase: Record<string, EvalCaseRunDetail>;
}>();

defineEmits<{ select: [caseVersionId: string] }>();

type CaseQueueRow = {
  item: EvalSetCase;
  run?: EvalCaseRunDetail;
  state: RunnerState;
  hint: string;
  preview: string;
};

const rows = computed<CaseQueueRow[]>(() =>
  props.cases.map((item) => {
    const run = props.runsByCase[item.case_version.id];
    const state = runnerState(run);
    return {
      item,
      run,
      state,
      hint: runActivityHint(run),
      preview: rowPreview(item, run, state),
    };
  }),
);

const activeCount = computed(() => rows.value.filter((row) => row.state.kind === "queued" || row.state.kind === "running").length);

function rowPreview(item: EvalSetCase, run: EvalCaseRunDetail | undefined, state: RunnerState): string {
  if (state.kind === "failed") return run?.eval_case_run.error || run?.job?.error || state.helper;
  if (state.kind === "running") return "Opencode 测评器正在处理，等待写入 result.json。";
  if (state.kind === "queued") return "任务已入队，等待后台进程领取。";
  const output = run?.result_artifact?.content_text?.trim();
  if (output) return output;
  return item.case_version.input_artifact.content_text?.trim() || "暂无输入内容。";
}
</script>

<template>
  <aside class="manual-case-list">
    <header class="manual-list-head">
      <div>
        <h2>测试例列表</h2>
        <p>{{ pending }} 个待评估，{{ activeCount }} 个进行中</p>
      </div>
      <span>{{ cases.length }}</span>
    </header>
    <div v-if="cases.length === 0" class="runner-case-empty">
      当前测评集还没有测试例。
    </div>
    <button
      v-for="(row, index) in rows"
      :key="row.item.case_version.id"
      :class="clsx('manual-case-row', 'runner-case-row', row.state.kind, activeCaseId === row.item.case_version.id && 'active')"
      type="button"
      @click="$emit('select', row.item.case_version.id)"
    >
      <span :class="clsx('manual-status-dot', row.state.kind)" aria-hidden="true" />
      <span class="manual-case-index">#{{ row.item.position + 1 }}</span>
      <span class="manual-case-copy runner-case-copy">
        <span class="runner-case-title-row">
          <strong>{{ row.item.case.title }}</strong>
          <RunnerStatusChip :kind="row.state.kind" :label="row.state.label" />
        </span>
        <span class="runner-case-preview">{{ row.preview }}</span>
        <span class="runner-case-meta" aria-label="测试例运行信息">
          <span>{{ promptSourceLabel(row.item) }}</span>
          <span>{{ modelLabel(row.item) }}</span>
          <span>尝试 {{ row.run?.job?.attempts ?? 0 }} 次</span>
          <span>{{ runTimeLabel(row.run) }}</span>
          <span v-if="row.hint" class="runner-live-hint">{{ row.hint }}</span>
        </span>
      </span>
      <kbd v-if="index < 9" class="manual-shortcut-chip">{{ index + 1 }}</kbd>
    </button>
  </aside>
</template>
