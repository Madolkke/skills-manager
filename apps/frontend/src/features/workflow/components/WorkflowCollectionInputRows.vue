<script setup lang="ts">
import type { WorkflowParameter } from "../../../types";
import WorkflowSchemaFieldRows from "./WorkflowSchemaFieldRows.vue";

const props = withDefaults(defineProps<{ items: WorkflowParameter[]; readonly: boolean; scalarOnly?: boolean }>(), { scalarOnly: false });
const emit = defineEmits<{
  change: [id: string, patch: Partial<WorkflowParameter>];
  remove: [id: string];
}>();
</script>

<template>
  <WorkflowSchemaFieldRows kind="input" :items="props.items" :readonly="props.readonly" :scalar-only="props.scalarOnly" @change="(id, patch) => emit('change', id, patch)" @remove="emit('remove', $event)" />
</template>
