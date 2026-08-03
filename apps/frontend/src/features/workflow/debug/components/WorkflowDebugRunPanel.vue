<script setup lang="ts">
import { Play, RefreshCw } from "lucide-vue-next";
import UiButton from "../../../../components/ui/UiButton.vue";
import type { WorkflowDebugRun } from "../../../../types";
import { humanDate } from "../../../../lib/format";
import { workflowDebugResultLabel, workflowDebugRunActive, workflowDebugRunLabel, workflowDebugRunTone } from "../presentation";

const props = defineProps<{
  currentRun: WorkflowDebugRun | null;
  history: WorkflowDebugRun[];
  nextCursor: string | null;
  startDisabled: boolean;
  startDisabledReason?: string;
  starting: boolean;
  advancing: boolean;
  historyLoading: boolean;
}>();
const emit = defineEmits<{ start: []; advance: []; select: [run: WorkflowDebugRun]; more: [] }>();
</script>

<template>
  <aside class="workflow-debug-run-panel">
    <div class="workflow-debug-run-actions">
      <div><h3>运行结果</h3><p>执行已保存调试例，并核对实际跳转。</p></div>
      <UiButton
        variant="primary"
        :state="props.starting ? 'loading' : 'idle'"
        :disabled="props.startDisabled"
        :disabled-reason="props.startDisabledReason"
        loading-label="启动中"
        @click="emit('start')"
      >
        <template #icon><Play /></template>
        开始调试
      </UiButton>
    </div>

    <section v-if="props.currentRun" class="workflow-debug-current-run" aria-live="polite">
      <div class="workflow-debug-current-head">
        <span :class="['workflow-debug-status', `is-${workflowDebugRunTone(props.currentRun)}`]">{{ workflowDebugResultLabel(props.currentRun) }}</span>
        <time :datetime="props.currentRun.updated_at">{{ humanDate(props.currentRun.updated_at) }}</time>
      </div>
      <dl class="workflow-debug-run-meta">
        <div><dt>状态</dt><dd>{{ workflowDebugRunLabel(props.currentRun.status) }}</dd></div>
        <div><dt>运行 ID</dt><dd>{{ props.currentRun.executor_run_id || "尚未取得" }}</dd></div>
        <div><dt>Workflow revision</dt><dd>{{ props.currentRun.workflow_revision }}</dd></div>
      </dl>
      <div v-if="props.currentRun.error" class="workflow-debug-run-error">
        <strong>{{ props.currentRun.error.code }}</strong>
        <p>{{ props.currentRun.error.message }}</p>
      </div>
      <UiButton
        v-if="props.currentRun.error?.retryable"
        size="sm"
        :state="props.advancing ? 'loading' : 'idle'"
        loading-label="重试中"
        @click="emit('advance')"
      >
        <template #icon><RefreshCw /></template>
        重新查询执行器
      </UiButton>
      <details v-if="props.currentRun.latest_executor_status" class="workflow-debug-raw-status">
        <summary>执行器原始状态</summary>
        <pre>{{ JSON.stringify(props.currentRun.latest_executor_status, null, 2) }}</pre>
      </details>
    </section>
    <div v-else class="workflow-debug-empty-run">尚未运行此调试例。</div>

    <section class="workflow-debug-history">
      <div class="workflow-debug-history-head"><h3>运行历史</h3><span>{{ props.history.length }} 条</span></div>
      <div v-if="props.history.length" class="workflow-debug-history-list">
        <button v-for="run in props.history" :key="run.id" type="button" :class="{ active: props.currentRun?.id === run.id }" :disabled="workflowDebugRunActive(props.currentRun) && props.currentRun?.id !== run.id" @click="emit('select', run)">
          <span :class="['workflow-debug-history-mark', `is-${workflowDebugRunTone(run)}`]" />
          <span><strong>{{ workflowDebugResultLabel(run) }}</strong><small>{{ humanDate(run.created_at) }}</small></span>
        </button>
      </div>
      <p v-else class="workflow-debug-empty-inline">暂无历史运行。</p>
      <UiButton v-if="props.nextCursor" size="sm" :state="props.historyLoading ? 'loading' : 'idle'" loading-label="加载中" @click="emit('more')">加载更多</UiButton>
    </section>
  </aside>
</template>
