<script setup lang="ts">
import { Play } from "lucide-vue-next";
import { computed } from "vue";
import RunnerDetailPanel from "./RunnerDetailPanel.vue";
import { modelLabel, promptSourceLabel, type RunnerState } from "../lib/evalRunner";
import type { EvalCaseRunDetail, EvalSetCase } from "../types";

const props = defineProps<{
  active: EvalSetCase | null;
  actualOutput: string;
  pollIntervalSeconds: number;
  polling: boolean;
  run: EvalCaseRunDetail | null;
  runningCaseId: string | null;
  state: RunnerState;
}>();

defineEmits<{
  copy: [label: string, text?: string | null];
  run: [];
}>();

const runButtonLabel = computed(() => {
  if (props.active && props.runningCaseId === props.active.case_version.id) return "入队中...";
  if (props.state.kind === "queued") return "排队中";
  if (props.state.kind === "running") return "运行中";
  return "运行此测试例";
});

const runButtonDisabled = computed(() => {
  if (!props.active) return true;
  return props.runningCaseId === props.active.case_version.id || props.state.kind === "queued" || props.state.kind === "running";
});
</script>

<template>
  <section class="manual-case-detail">
    <template v-if="active">
      <header class="manual-case-head">
        <div>
          <span>测试例 #{{ active.position + 1 }}</span>
          <h2>{{ active.case.title }}</h2>
          <p class="manual-case-subtitle">
            {{ promptSourceLabel(active) }} · {{ modelLabel(active) }}
          </p>
        </div>
        <div class="button-row">
          <button class="secondary-button" type="button" :disabled="runButtonDisabled" @click="$emit('run')">
            <Play :size="16" />
            {{ runButtonLabel }}
          </button>
          <button class="secondary-button" type="button" @click="$emit('copy', '测试输入', active.case_version.input_artifact.content_text)">复制测试输入</button>
          <button class="secondary-button" type="button" @click="$emit('copy', '预期结果', active.case_version.expected_output_artifact.content_text)">复制预期结果</button>
        </div>
      </header>
      <div class="manual-comparison-grid">
        <section><h3>测试输入</h3><pre>{{ active.case_version.input_artifact.content_text }}</pre></section>
        <section><h3>预期结果</h3><pre>{{ active.case_version.expected_output_artifact.content_text }}</pre></section>
      </div>
      <RunnerDetailPanel
        :actual-output="actualOutput"
        :poll-interval-seconds="pollIntervalSeconds"
        :polling="polling"
        :run="run"
        :state="state"
        @copy="(label, text) => $emit('copy', label, text)"
      />
    </template>
    <div v-else class="runner-detail-placeholder">
      <strong>选择一个测试例查看详情</strong>
      <p>左侧列表会持续显示任务状态。点击某一行后，这里会展示测试输入、预期结果、运行结果和测评器信息。</p>
    </div>
  </section>
</template>
