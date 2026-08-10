<script setup lang="ts">
import { ChevronRight, FileCheck2 } from "lucide-vue-next";
import type { WorkflowAgentProposal } from "../../../../types";

const props = defineProps<{ proposal: WorkflowAgentProposal }>();
defineEmits<{ open: [] }>();
const labels = { proposed: "待确认", applied: "已创建", stale: "已过期" } as const;
</script>

<template>
  <button type="button" :class="['workflow-agent-proposal-summary', `is-${props.proposal.status}`]" @click="$emit('open')">
    <FileCheck2 :size="17" />
    <span><strong>{{ props.proposal.payload.candidates.length }} 个调试例候选</strong><small>{{ labels[props.proposal.status] }}</small></span>
    <ChevronRight :size="17" />
  </button>
</template>
