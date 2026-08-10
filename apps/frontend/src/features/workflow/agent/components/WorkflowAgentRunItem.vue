<script setup lang="ts">
import { Ban, CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-vue-next";
import type { WorkflowAgentRun } from "../../../../types";
import MarkdownContent from "../../../skill-builder/components/MarkdownContent.vue";
import type { WorkflowAgentTimelineEntry } from "../timelineEntries";
import WorkflowAgentEventFeed from "./WorkflowAgentEventFeed.vue";
import WorkflowAgentProposalSummary from "./WorkflowAgentProposalSummary.vue";

const props = defineProps<{
  run: WorkflowAgentRun;
  current: boolean;
  agentName: string;
  entries: WorkflowAgentTimelineEntry[];
}>();
defineEmits<{ select: [run: WorkflowAgentRun]; proposal: [run: WorkflowAgentRun] }>();

const statusLabels: Record<WorkflowAgentRun["status"], string> = {
  starting: "准备中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
  interrupted: "已中断",
};

function timeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}
</script>

<template>
  <article :class="['workflow-agent-turn', props.current && 'is-current', `is-${props.run.status}`]" :data-run-id="props.run.id">
    <button type="button" class="workflow-agent-turn-head" :aria-current="props.current || undefined" :aria-expanded="props.current" @click="$emit('select', props.run)">
      <span class="workflow-agent-turn-identity">
        <LoaderCircle v-if="props.run.status === 'starting' || props.run.status === 'running'" class="workflow-agent-running-icon" :size="14" />
        <CheckCircle2 v-else-if="props.run.status === 'completed'" :size="14" />
        <XCircle v-else-if="props.run.status === 'failed'" :size="14" />
        <Ban v-else-if="props.run.status === 'canceled'" :size="14" />
        <CircleAlert v-else :size="14" />
        <strong>{{ props.agentName }}</strong>
      </span>
      <span class="workflow-agent-turn-meta"><time :datetime="props.run.created_at">{{ timeLabel(props.run.created_at) }}</time><small>{{ statusLabels[props.run.status] }}</small></span>
    </button>

    <div :class="['workflow-agent-user', !props.current && 'is-summary']">{{ props.run.user_input }}</div>
    <template v-if="props.current">
      <WorkflowAgentEventFeed v-if="props.entries.length" :entries="props.entries" />
      <MarkdownContent v-else-if="props.run.response_text" class="workflow-agent-answer" :source="props.run.response_text" />
    </template>
    <MarkdownContent v-else-if="props.run.response_text" class="workflow-agent-answer workflow-agent-answer-summary" :source="props.run.response_text" />
    <WorkflowAgentProposalSummary v-if="props.run.proposal" :proposal="props.run.proposal" @open="$emit('proposal', props.run)" />
    <p v-if="props.run.error" class="workflow-agent-run-error">{{ props.run.error.message ?? props.run.error.code }}</p>
  </article>
</template>
