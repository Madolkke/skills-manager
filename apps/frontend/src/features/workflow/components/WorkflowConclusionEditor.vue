<script setup lang="ts">
import { Flag, Trash2 } from "lucide-vue-next";
import type { WorkflowBundle, WorkflowConclusion } from "../../../types";
import WorkflowPredecessors from "./WorkflowPredecessors.vue";
const props = defineProps<{ conclusion: WorkflowConclusion; bundle: WorkflowBundle; readonly: boolean }>();
const emit = defineEmits<{ change: [patch: Partial<WorkflowConclusion>]; remove: []; "predecessor-open": [id: string] }>();
</script>

<template>
  <section class="workflow-document">
    <header class="workflow-document-head"><span><Flag :size="18" /></span><div><small>CONCLUSION</small><h2>{{ props.conclusion.name }}</h2><p>结论是流程终点，描述根因和修复建议。</p></div><button class="icon-button" type="button" aria-label="删除结论" :disabled="props.readonly" @click="emit('remove')"><Trash2 :size="16" /></button></header>
    <div class="workflow-form-grid"><label class="field-label span-2"><span>结论名称</span><input :value="props.conclusion.name" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label><label class="field-label span-2"><span>故障根因</span><textarea rows="6" :value="props.conclusion.rootCause" :disabled="props.readonly" @input="emit('change', { rootCause: ($event.target as HTMLTextAreaElement).value })" /></label><label class="field-label span-2"><span>修复建议</span><textarea rows="6" :value="props.conclusion.repairRecommendation" :disabled="props.readonly" @input="emit('change', { repairRecommendation: ($event.target as HTMLTextAreaElement).value })" /></label></div>
    <WorkflowPredecessors :bundle="props.bundle" :target-id="props.conclusion.id" @open="emit('predecessor-open', $event)" />
  </section>
</template>
