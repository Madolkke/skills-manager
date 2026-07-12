<script setup lang="ts">
import { ref } from "vue";
import Modal from "../../../components/Modal.vue";
import type { CollectionDefinition, WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import WorkflowPreviewPanel from "./WorkflowPreviewPanel.vue";

defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[]; issues: WorkflowValidationIssue[]; selection: WorkflowSelection }>();
const emit = defineEmits<{ close: []; select: [selection: WorkflowSelection] }>();
const tab = ref<"graph" | "read" | "validation">("graph");
</script>

<template>
  <Modal title="Workflow 预览" size="workspace" @close="emit('close')">
    <div class="workflow-full-preview">
      <WorkflowPreviewPanel v-model:tab="tab" :bundle="bundle" :catalog="catalog" :issues="issues" :selection="selection" @select="emit('select', $event)" />
    </div>
  </Modal>
</template>
