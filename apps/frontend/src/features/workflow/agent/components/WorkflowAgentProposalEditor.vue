<script setup lang="ts">
import type { WorkflowBundle, WorkflowDebugCasePayload, WorkflowStep } from "../../../../types";
import WorkflowDebugCaseEditor from "../../debug/components/WorkflowDebugCaseEditor.vue";

const props = defineProps<{ bundle: WorkflowBundle; step: WorkflowStep; candidates: WorkflowDebugCasePayload[]; selected: boolean[]; disabled?: boolean }>();
const emit = defineEmits<{ change: [index: number, candidate: WorkflowDebugCasePayload]; select: [index: number, selected: boolean] }>();
</script>

<template>
  <section class="workflow-agent-proposals">
    <header><div><strong>调试例候选</strong><small>确认后会以单个事务创建所选调试例。</small></div></header>
    <article v-for="(candidate, index) in props.candidates" :key="`${candidate.expected_target_id}-${index}`">
      <label class="workflow-agent-candidate-toggle"><input type="checkbox" :checked="props.selected[index]" :disabled="props.disabled" @change="emit('select', index, ($event.target as HTMLInputElement).checked)" />保存此候选</label>
      <WorkflowDebugCaseEditor :bundle="props.bundle" :step="props.step" :draft="candidate" :disabled="props.disabled || !props.selected[index]" @change="emit('change', index, $event)" />
    </article>
  </section>
</template>
