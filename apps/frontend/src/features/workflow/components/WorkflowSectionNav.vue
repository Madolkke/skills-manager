<script setup lang="ts">
import { AlertTriangle } from "lucide-vue-next";
import type { WorkflowEditorSection } from "../../../types";

defineProps<{
  active: WorkflowEditorSection;
  sections: Array<{ id: WorkflowEditorSection; label: string; issues: number }>;
}>();
const emit = defineEmits<{ select: [section: WorkflowEditorSection] }>();
</script>

<template>
  <nav class="workflow-section-nav" aria-label="步骤编辑区块">
    <button v-for="item in sections" :key="item.id" :class="active === item.id && 'active'" type="button" @click="emit('select', item.id)">
      {{ item.label }}
      <span v-if="item.issues"><AlertTriangle :size="10" />{{ item.issues }}</span>
    </button>
  </nav>
</template>
