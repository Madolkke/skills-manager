<script setup lang="ts">
import { Trash2 } from "lucide-vue-next";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionOutput } from "../../../types";

const props = defineProps<{ items: CollectionOutput[]; readonly: boolean }>();
const emit = defineEmits<{
  change: [id: string, patch: Partial<CollectionOutput>];
  remove: [id: string];
}>();
const dataTypes = ["string", "integer", "number", "boolean", "array", "object"];
</script>

<template>
  <div v-if="props.items.length" class="workflow-field-table">
    <div class="workflow-field-table-head workflow-collection-output-grid" aria-hidden="true">
      <span>字段名称（Key）</span><span>类型</span><span>字段说明</span><span></span>
    </div>
    <div v-for="item in props.items" :key="item.id" class="workflow-field-table-row workflow-collection-output-grid">
      <input class="workflow-key-input" :value="item.key" aria-label="字段名称（Key）" placeholder="version" :disabled="props.readonly" @input="emit('change', item.id, { key: ($event.target as HTMLInputElement).value })" />
      <select :value="item.dataType" aria-label="字段类型" :disabled="props.readonly" @change="emit('change', item.id, { dataType: ($event.target as HTMLSelectElement).value })"><option v-for="type in dataTypes" :key="type" :value="type">{{ type }}</option></select>
      <input :value="item.description" aria-label="字段说明" placeholder="说明该字段表示的采集结果" :disabled="props.readonly" @input="emit('change', item.id, { description: ($event.target as HTMLInputElement).value })" />
      <UiIconButton label="删除输出" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 /></UiIconButton>
    </div>
  </div>
</template>
