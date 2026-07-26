<script setup lang="ts">
import type { WorkflowParameter } from "../../../types";
import WorkflowSchemaFieldRows from "./WorkflowSchemaFieldRows.vue";

const props = defineProps<{ items: WorkflowParameter[]; readonly: boolean }>();
const emit = defineEmits<{
  change: [id: string, patch: Partial<WorkflowParameter>];
  remove: [id: string];
}>();
</script>

<template>
  <WorkflowSchemaFieldRows kind="input" :items="props.items" :readonly="props.readonly" @change="(id, patch) => emit('change', id, patch)" @remove="emit('remove', $event)" />
</template>
