<script setup lang="ts">
import { Pencil, Trash2 } from "lucide-vue-next";
import { computed, ref } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionOutput, WorkflowJsonSchema, WorkflowParameter } from "../../../types";
import { workflowSchemaSummary, workflowSchemaTitle } from "../workflowJsonSchema";
import WorkflowSchemaEditorModal from "./WorkflowSchemaEditorModal.vue";

type SchemaField = WorkflowParameter | CollectionOutput;
const props = defineProps<{ items: SchemaField[]; readonly: boolean; kind: "input" | "output" }>();
const emit = defineEmits<{ change: [id: string, patch: Partial<SchemaField>]; remove: [id: string] }>();
const editingId = ref<string | null>(null);
const editing = computed(() => props.items.find((item) => item.id === editingId.value));

function confirm(schema: WorkflowJsonSchema): void {
  if (editingId.value) emit("change", editingId.value, { schema });
  editingId.value = null;
}
</script>

<template>
  <div v-if="props.items.length" class="workflow-field-table workflow-schema-field-table">
    <div class="workflow-field-table-head workflow-schema-field-grid" aria-hidden="true">
      <span>字段 Key</span><span>显示名称</span><span>Schema</span><span>必填</span><span></span>
    </div>
    <div v-for="item in props.items" :key="item.id" class="workflow-field-table-row workflow-schema-field-grid">
      <input class="workflow-key-input" :value="item.key" :aria-label="props.kind === 'input' ? '参数 Key' : '字段名称（Key）'" :placeholder="props.kind === 'input' ? 'interface_name' : 'version'" :disabled="props.readonly" @input="emit('change', item.id, { key: ($event.target as HTMLInputElement).value })" />
      <span class="workflow-schema-field-title"><strong>{{ workflowSchemaTitle(item.schema, item.key || "未命名") }}</strong><small>{{ item.schema.description || "暂无说明" }}</small></span>
      <code>{{ workflowSchemaSummary(item.schema) }}</code>
      <label class="workflow-check workflow-field-required"><input type="checkbox" :checked="item.required" :disabled="props.readonly" @change="emit('change', item.id, { required: ($event.target as HTMLInputElement).checked })" /><span class="sr-only">必填</span></label>
      <div class="workflow-row-actions"><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="editingId = item.id"><template #icon><Pencil /></template>编辑</UiButton><UiIconButton :label="props.kind === 'input' ? '删除输入' : '删除输出'" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 /></UiIconButton></div>
    </div>
  </div>
  <WorkflowSchemaEditorModal v-if="editing" :open="Boolean(editing)" :schema="editing.schema" :field-key="editing.key" :readonly="props.readonly" @close="editingId = null" @confirm="confirm" />
</template>
