<script setup lang="ts">
import { ArrowUpRight, GitBranch, TerminalSquare } from "lucide-vue-next";
import type { WorkflowBundle } from "../../../types";
import { workflowPredecessors } from "../domain/utils";

const props = defineProps<{ bundle: WorkflowBundle; targetId: string }>();
const emit = defineEmits<{ open: [id: string] }>();
</script>

<template>
  <section class="workflow-predecessors">
    <div class="workflow-predecessors-head"><span><GitBranch :size="14" />前序节点</span><small>{{ workflowPredecessors(props.bundle, props.targetId).length }} 个直接来源</small></div>
    <div v-if="workflowPredecessors(props.bundle, props.targetId).length" class="workflow-predecessors-list">
      <button v-for="step in workflowPredecessors(props.bundle, props.targetId)" :key="step.id" type="button" @click="emit('open', step.id)"><TerminalSquare :size="14" /><span><strong>{{ step.name }}</strong><small>{{ step.description || "未填写说明" }}</small></span><ArrowUpRight :size="14" /></button>
    </div>
    <p v-else>当前没有节点跳转到这里。</p>
  </section>
</template>
