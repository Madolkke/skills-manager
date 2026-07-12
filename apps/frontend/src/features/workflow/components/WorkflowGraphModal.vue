<script setup lang="ts">
import Modal from "../../../components/Modal.vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import WorkflowGraph from "./WorkflowGraph.vue";

const props = withDefaults(defineProps<{ open?: boolean; bundle: WorkflowBundle; issues: WorkflowValidationIssue[]; selection: WorkflowSelection; direction: "DOWN" | "RIGHT" }>(), { open: true });
const emit = defineEmits<{ close: []; closed: []; select: [selection: WorkflowSelection]; "update:direction": [direction: "DOWN" | "RIGHT"] }>();
</script>

<template>
  <Modal title="流程图预览" size="workspace" :open="props.open" motion="workflow" @close="emit('close')" @after-leave="emit('closed')">
    <div class="workflow-graph-modal"><WorkflowGraph v-if="props.open" :bundle="props.bundle" :issues="props.issues" :selected="props.selection" :direction="props.direction" @select="emit('select', $event)" @update:direction="emit('update:direction', $event)" /></div>
  </Modal>
</template>
