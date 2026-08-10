<script setup lang="ts">
import { computed } from "vue";
import { CheckCircle2, ChevronDown, CircleEllipsis, Wrench, XCircle } from "lucide-vue-next";
import type { WorkflowAgentToolEntry } from "../timelineEntries";

const props = defineProps<{ entry: WorkflowAgentToolEntry }>();
const hasDetails = computed(() => Boolean(props.entry.arguments || props.entry.result));

function statusLabel(): string {
  return { calling: "调用中", running: "执行中", success: "成功", failure: "失败" }[props.entry.phase];
}

function handleSummaryClick(event: MouseEvent): void {
  if (!hasDetails.value) event.preventDefault();
}
</script>

<template>
  <details :class="['workflow-agent-tool-entry', `is-${props.entry.phase}`, !hasDetails && 'is-empty']">
    <summary @click="handleSummaryClick">
      <Wrench :size="14" />
      <strong>{{ props.entry.name }}</strong>
      <span>{{ statusLabel() }}</span>
      <CheckCircle2 v-if="props.entry.phase === 'success'" class="workflow-agent-tool-status-icon" :size="14" />
      <XCircle v-else-if="props.entry.phase === 'failure'" class="workflow-agent-tool-status-icon" :size="14" />
      <CircleEllipsis v-else class="workflow-agent-tool-status-icon" :size="14" />
      <ChevronDown v-if="hasDetails" class="workflow-agent-tool-chevron" :size="14" />
    </summary>
    <div v-if="props.entry.arguments || props.entry.result" class="workflow-agent-tool-details">
      <section v-if="props.entry.arguments"><h4>调用参数</h4><pre>{{ props.entry.arguments }}</pre></section>
      <section v-if="props.entry.result"><h4>执行结果</h4><pre>{{ props.entry.result }}</pre></section>
    </div>
  </details>
</template>
