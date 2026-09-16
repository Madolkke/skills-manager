<script setup lang="ts">
import type { WorkflowParameter } from "../../../types";
import WorkflowSchemaFieldRows from "./WorkflowSchemaFieldRows.vue";

const props = withDefaults(defineProps<{ items: WorkflowParameter[]; readonly: boolean; identityReadonly?: boolean; scalarOnly?: boolean; commandParameterKeys?: string[] }>(), { scalarOnly: false, commandParameterKeys: () => [] });
const emit = defineEmits<{
  change: [id: string, patch: Partial<WorkflowParameter>];
  remove: [id: string];
}>();
</script>

<template>
  <WorkflowSchemaFieldRows kind="input" :items="props.items" :readonly="props.readonly" :identity-readonly="props.identityReadonly" :scalar-only="props.scalarOnly" :highlighted-keys="props.commandParameterKeys" @change="(id, patch) => emit('change', id, patch)" @remove="emit('remove', $event)" />
</template>
