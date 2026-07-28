<script setup lang="ts">
import type { CollectionOutput } from "../../../types";
import WorkflowSchemaFieldRows from "./WorkflowSchemaFieldRows.vue";

const props = defineProps<{ items: CollectionOutput[]; readonly: boolean }>();
const emit = defineEmits<{
  change: [id: string, patch: Partial<CollectionOutput>];
  remove: [id: string];
}>();
</script>

<template>
  <WorkflowSchemaFieldRows kind="output" :items="props.items" :readonly="props.readonly" @change="(id, patch) => emit('change', id, patch)" @remove="emit('remove', $event)" />
</template>
