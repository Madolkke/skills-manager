<script setup lang="ts">
import { Brain, Code2 } from "lucide-vue-next";
import MarkdownContent from "../../../skill-builder/components/MarkdownContent.vue";
import type { WorkflowAgentTimelineEntry } from "../timelineEntries";
import WorkflowAgentToolEntry from "./WorkflowAgentToolEntry.vue";

defineProps<{ entries: WorkflowAgentTimelineEntry[] }>();
</script>

<template>
  <div class="workflow-agent-event-feed" aria-live="polite">
    <template v-for="entry in entries" :key="entry.key">
      <details v-if="entry.kind === 'thinking'" class="workflow-agent-thinking-entry"><summary><Brain :size="14" />思考过程</summary><pre>{{ entry.text }}</pre></details>
      <WorkflowAgentToolEntry v-else-if="entry.kind === 'tool'" :entry="entry" />
      <MarkdownContent v-else-if="entry.kind === 'text'" class="workflow-agent-answer workflow-agent-text-entry" :source="entry.text" />
      <section v-else class="workflow-agent-data-entry"><header><Code2 :size="14" />结构化输出</header><pre>{{ entry.content }}</pre></section>
    </template>
  </div>
</template>
