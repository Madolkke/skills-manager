<script setup lang="ts">
import { Play } from "lucide-vue-next";
import { computed } from "vue";
import OpencodeTraceDetails from "./OpencodeTraceDetails.vue";
import RunnerDetailPanel from "./RunnerDetailPanel.vue";
import { modelLabel, promptSourceLabel, stepTimelineRows, type RunnerState } from "../lib/evalRunner";
import type { EvalCaseRunDetail, EvalSetCase } from "../../../types";

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
  <section class="runner-case-detail">
    <template v-if="active">
      <header class="runner-case-head">
        <div>
          <span>测试例 #{{ active.position + 1 }}</span>
          <h2>{{ active.case.title }}</h2>
          <p class="runner-case-subtitle">
            {{ promptSourceLabel(active) }} · {{ modelLabel(active) }}
          </p>
        </div>
        <div class="button-row">
          <button class="secondary-button" type="button" :disabled="runButtonDisabled" @click="$emit('run')">
            <Play :size="16" />
            {{ runButtonLabel }}
          </button>
          <button class="secondary-button" type="button" @click="$emit('copy', '测试步骤', JSON.stringify(active.case_version.steps, null, 2))">复制测试步骤</button>
        </div>
      </header>
      <section class="runner-step-list" aria-label="测试步骤时间线">
        <article v-for="step in stepTimelineRows(active, run)" :key="step.id" :class="['runner-step-card', step.status]">
          <header>
            <strong>{{ step.title }}</strong>
            <span>{{ step.label }}</span>
          </header>
          <small>{{ step.assertions.length }} 个判断条件</small>
          <pre>{{ step.input }}</pre>
          <p v-if="step.reason">{{ step.reason }}</p>
          <div class="runner-step-assertions">
            <article v-for="assertion in step.assertions" :key="assertion.id" :class="['runner-assertion-card', assertion.status]">
              <header>
                <strong>{{ assertion.assertionTemplateId }}</strong>
                <span>{{ assertion.label }}</span>
              </header>
              <p v-if="assertion.reason">{{ assertion.reason }}</p>
              <pre v-if="assertion.actual">{{ assertion.actual }}</pre>
            </article>
          </div>
          <pre v-if="step.actual">{{ step.actual }}</pre>
          <OpencodeTraceDetails :trace="step.opencodeTrace" />
        </article>
      </section>
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
      <p>左侧列表会持续显示任务状态。点击某一行后，这里会展示测试步骤、判断条件、运行结果和测评器信息。</p>
    </div>
  </section>
</template>
