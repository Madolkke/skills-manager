<script setup lang="ts">
import clsx from "clsx";
import { Copy } from "lucide-vue-next";
import type { EvalCaseRunDetail } from "../../../types";
import { emptyActualOutputText, metadataText, runError, runnerStatusRows, type RunnerState } from "../lib/evalRunner";
import RunnerStatusChip from "./RunnerStatusChip.vue";

const props = defineProps<{
  actualOutput: string;
  pollIntervalSeconds: number;
  polling: boolean;
  run: EvalCaseRunDetail | null;
  state: RunnerState;
}>();

defineEmits<{ copy: [label: string, text: string] }>();
</script>

<template>
  <div class="runner-detail-grid">
    <section :class="clsx('runner-output-panel', state.kind)">
      <div v-if="state.kind === 'running'" class="runner-activity-bar" role="status">
        <span aria-hidden="true" />
        Opencode 测评器正在处理此测试例
      </div>
      <header>
        <div>
          <RunnerStatusChip :kind="state.kind" :label="state.label" />
          <h3>运行结果</h3>
        </div>
        <button class="secondary-button compact-button" type="button" :disabled="!actualOutput.trim()" @click="$emit('copy', '运行结果', actualOutput)">
          <Copy :size="15" />
          复制结果
        </button>
      </header>
      <pre :class="!actualOutput.trim() && 'empty'">{{ actualOutput.trim() ? actualOutput : emptyActualOutputText(state) }}</pre>
    </section>
    <section class="runner-inspector-panel">
      <header>
        <div>
          <span>测评器状态</span>
          <h3>{{ state.helper }}</h3>
        </div>
        <span class="tag-chip muted">{{ polling ? "正在刷新任务状态" : `轮询 ${pollIntervalSeconds}s` }}</span>
      </header>
      <dl class="runner-status-list">
        <div v-for="row in runnerStatusRows(run)" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </div>
      </dl>
      <div v-if="metadataText(run, 'reason')" class="runner-message">
        <strong>原因</strong>
        <p>{{ metadataText(run, "reason") }}</p>
      </div>
      <div v-if="runError(run)" class="runner-message error">
        <strong>错误</strong>
        <p>{{ runError(run) }}</p>
      </div>
      <div v-if="!run" class="runner-empty-state">
        当前测试例还没有任务。点击“运行此测试例”或底部“运行全部”后会开始追踪。
      </div>
    </section>
  </div>
</template>
