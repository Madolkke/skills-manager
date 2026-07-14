<script setup lang="ts">
import { Trash2 } from "lucide-vue-next";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowParameter } from "../../../types";

const props = defineProps<{ items: WorkflowParameter[]; readonly: boolean }>();
const emit = defineEmits<{
  change: [id: string, patch: Partial<WorkflowParameter>];
  remove: [id: string];
}>();
const dataTypes = ["string", "integer", "number", "boolean", "array", "object"];
</script>

<template>
  <div v-if="props.items.length" class="workflow-field-table">
    <div class="workflow-field-table-head workflow-collection-input-grid" aria-hidden="true">
      <span>参数 Key</span><span>参数名称</span><span>类型</span><span>参数说明</span><span>必填</span><span></span>
    </div>
    <div v-for="item in props.items" :key="item.id" class="workflow-field-table-row workflow-collection-input-grid">
      <input class="workflow-key-input" :value="item.key" aria-label="参数 Key" placeholder="interface_name" :disabled="props.readonly" @input="emit('change', item.id, { key: ($event.target as HTMLInputElement).value })" />
      <input :value="item.name" aria-label="参数名称" placeholder="接口名称" :disabled="props.readonly" @input="emit('change', item.id, { name: ($event.target as HTMLInputElement).value })" />
      <select :value="item.dataType" aria-label="参数类型" :disabled="props.readonly" @change="emit('change', item.id, { dataType: ($event.target as HTMLSelectElement).value })"><option v-for="type in dataTypes" :key="type" :value="type">{{ type }}</option></select>
      <input :value="item.description" aria-label="参数说明" placeholder="说明参数在命令中的用途" :disabled="props.readonly" @input="emit('change', item.id, { description: ($event.target as HTMLInputElement).value })" />
      <label class="workflow-check workflow-field-required"><input type="checkbox" :checked="item.required" :disabled="props.readonly" @change="emit('change', item.id, { required: ($event.target as HTMLInputElement).checked })" /><span class="sr-only">必填</span></label>
      <UiIconButton label="删除输入" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 /></UiIconButton>
    </div>
  </div>
</template>
