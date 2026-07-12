<script setup lang="ts">
import Modal from "../../../components/Modal.vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import WorkflowGraph from "./WorkflowGraph.vue";

const props = defineProps<{ bundle: WorkflowBundle; issues: WorkflowValidationIssue[]; selection: WorkflowSelection; direction: "DOWN" | "RIGHT" }>();
const emit = defineEmits<{ close: []; select: [selection: WorkflowSelection]; "update:direction": [direction: "DOWN" | "RIGHT"] }>();
</script>

<template>
  <Modal title="流程图预览" size="workspace" @close="emit('close')">
    <div class="workflow-graph-modal"><WorkflowGraph :bundle="props.bundle" :issues="props.issues" :selected="props.selection" :direction="props.direction" @select="emit('select', $event)" @update:direction="emit('update:direction', $event)" /></div>
  </Modal>
</template>
