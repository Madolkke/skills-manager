<script setup lang="ts">
import { computed } from "vue";
import { Bot, Brain, CheckCircle2, CircleEllipsis, Wrench } from "lucide-vue-next";
import type { WorkflowAgentDescriptor, WorkflowAgentEvent, WorkflowAgentRun } from "../../../../types";
import MarkdownContent from "../../../skill-builder/components/MarkdownContent.vue";

const props = defineProps<{ runs: WorkflowAgentRun[]; currentRun: WorkflowAgentRun | null; events: WorkflowAgentEvent[]; agents: WorkflowAgentDescriptor[] }>();
defineEmits<{ select: [run: WorkflowAgentRun] }>();
const thinking = computed(() => deltas("THINKING_BLOCK_DELTA"));
const streamingText = computed(() => deltas("TEXT_BLOCK_DELTA"));
const tools = computed(() => props.events.filter((item) => item.event.type === "TOOL_CALL_START" || item.event.type === "TOOL_RESULT_END"));

function deltas(type: string): string {
  return props.events.filter((item) => item.event.type === type).map((item) => String(item.event.delta ?? "")).join("");
}
function agentName(id: string): string {
  return props.agents.find((item) => item.id === id)?.name ?? id;
}
function statusLabel(status: WorkflowAgentRun["status"]): string {
  return { starting: "准备中", running: "运行中", completed: "已完成", failed: "失败", canceled: "已取消", interrupted: "已中断" }[status];
}
</script>

<template>
  <div class="workflow-agent-timeline" aria-live="polite">
    <div v-if="!props.runs.length" class="workflow-agent-empty"><Bot :size="24" /><strong>从当前 Workflow 开始提问</strong><span>助手可读取草稿、校验结果、相关采集定义和已有调试例。</span></div>
    <article v-for="run in props.runs" :key="run.id" :class="['workflow-agent-turn', props.currentRun?.id === run.id && 'is-current']">
      <button type="button" class="workflow-agent-turn-head" @click="$emit('select', run)"><span>{{ agentName(run.agent_id) }}</span><small>{{ statusLabel(run.status) }}</small></button>
      <div class="workflow-agent-user">{{ run.user_input }}</div>
      <template v-if="props.currentRun?.id === run.id">
        <details v-if="thinking" class="workflow-agent-thinking"><summary><Brain :size="14" />思考过程</summary><pre>{{ thinking }}</pre></details>
        <div v-if="tools.length" class="workflow-agent-tools">
          <div v-for="item in tools" :key="item.event_id"><Wrench :size="13" /><span>{{ item.event.tool_call_name ?? "领域工具" }}</span><CheckCircle2 v-if="item.event.type === 'TOOL_RESULT_END'" :size="13" /><CircleEllipsis v-else :size="13" /></div>
        </div>
        <MarkdownContent v-if="streamingText || run.response_text" class="workflow-agent-answer" :source="streamingText || run.response_text" />
      </template>
      <MarkdownContent v-else-if="run.response_text" class="workflow-agent-answer" :source="run.response_text" />
      <p v-if="run.error" class="workflow-agent-run-error">{{ run.error.message ?? run.error.code }}</p>
    </article>
  </div>
</template>
