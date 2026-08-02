<script setup lang="ts">
import { Pencil, Trash2 } from "lucide-vue-next";
import { computed, ref } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionOutput, WorkflowJsonSchema, WorkflowParameter } from "../../../types";
import {
  changeWorkflowSchemaEditorType,
  workflowSchemaEditorType,
  workflowSchemaSummary,
  type WorkflowSchemaEditorType,
} from "../workflowJsonSchema";
import WorkflowConfirmModal from "./WorkflowConfirmModal.vue";
import WorkflowSchemaEditorModal from "./WorkflowSchemaEditorModal.vue";

type SchemaField = WorkflowParameter | CollectionOutput;
const props = defineProps<{ items: SchemaField[]; readonly: boolean; kind: "input" | "output" }>();
const emit = defineEmits<{ change: [id: string, patch: Partial<SchemaField>]; remove: [id: string] }>();
const editingId = ref<string | null>(null);
const editing = computed(() => props.items.find((item) => item.id === editingId.value));
const pendingType = ref<{ id: string; type: WorkflowSchemaEditorType } | null>(null);
const editorTypes: Array<{ value: WorkflowSchemaEditorType; label: string }> = [
  { value: "string", label: "string" },
  { value: "integer", label: "integer" },
  { value: "number", label: "number" },
  { value: "boolean", label: "boolean" },
  { value: "string-array", label: "字符串数组（string[]）" },
  { value: "complex", label: "复杂对象" },
];

function changeType(item: SchemaField, type: WorkflowSchemaEditorType): void {
  const current = workflowSchemaEditorType(item.schema);
  if (type === current) return;
  if (current === "complex" && type !== "complex") {
    pendingType.value = { id: item.id, type };
    return;
  }
  emit("change", item.id, { schema: changeWorkflowSchemaEditorType(item.schema, type) });
}

function confirmTypeChange(): void {
  const pending = pendingType.value;
  const item = props.items.find((candidate) => candidate.id === pending?.id);
  if (pending && item) emit("change", item.id, { schema: changeWorkflowSchemaEditorType(item.schema, pending.type) });
  pendingType.value = null;
}

function updateSchemaMetadata(item: SchemaField, field: "title" | "description", value: string): void {
  emit("change", item.id, { schema: { ...item.schema, [field]: value } });
}

function confirm(schema: WorkflowJsonSchema): void {
  if (editingId.value) emit("change", editingId.value, { schema });
  editingId.value = null;
}
</script>

<template>
  <div v-if="props.items.length" class="workflow-field-table workflow-schema-field-table">
    <div class="workflow-field-table-head workflow-schema-field-grid" aria-hidden="true">
      <span>变量名</span><span>类型</span><span>显示名称</span><span>说明</span><span></span>
    </div>
    <div v-for="item in props.items" :key="item.id" class="workflow-field-table-row workflow-schema-field-grid">
      <label class="workflow-schema-inline-field">
        <span>变量名</span>
        <input class="workflow-key-input" :value="item.key" :aria-label="props.kind === 'input' ? '参数变量名' : '输出变量名'" :placeholder="props.kind === 'input' ? 'interface_name' : 'version'" :disabled="props.readonly" @input="emit('change', item.id, { key: ($event.target as HTMLInputElement).value })" />
      </label>
      <label class="workflow-schema-inline-field workflow-schema-type-field">
        <span>类型</span>
        <select :value="workflowSchemaEditorType(item.schema)" :aria-label="props.kind === 'input' ? '参数类型' : '字段类型'" :disabled="props.readonly" @change="changeType(item, ($event.target as HTMLSelectElement).value as WorkflowSchemaEditorType)">
          <option v-for="type in editorTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
        </select>
        <small v-if="workflowSchemaEditorType(item.schema) === 'complex'">{{ workflowSchemaSummary(item.schema) }}</small>
      </label>
      <label class="workflow-schema-inline-field">
        <span>显示名称</span>
        <input :value="item.schema.title ?? ''" :aria-label="props.kind === 'input' ? '参数显示名称' : '字段显示名称'" placeholder="字段名称" :disabled="props.readonly" @input="updateSchemaMetadata(item, 'title', ($event.target as HTMLInputElement).value)" />
      </label>
      <label class="workflow-schema-inline-field">
        <span>说明</span>
        <input :value="item.schema.description ?? ''" :aria-label="props.kind === 'input' ? '参数说明' : '字段说明'" placeholder="字段用途（可选）" :disabled="props.readonly" @input="updateSchemaMetadata(item, 'description', ($event.target as HTMLInputElement).value)" />
      </label>
      <div class="workflow-row-actions">
        <UiIconButton v-if="workflowSchemaEditorType(item.schema) === 'complex'" :label="item.schema['x-skillhub-legacy-loose'] ? '完善 Schema' : '配置 Schema'" size="sm" variant="secondary" :disabled="props.readonly" @click="editingId = item.id"><Pencil /></UiIconButton>
        <UiIconButton :label="props.kind === 'input' ? '删除输入' : '删除输出'" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 /></UiIconButton>
      </div>
    </div>
  </div>
  <WorkflowSchemaEditorModal v-if="editing && workflowSchemaEditorType(editing.schema) === 'complex'" :open="true" :schema="editing.schema" :field-key="editing.key" :readonly="props.readonly" @close="editingId = null" @confirm="confirm" />
  <WorkflowConfirmModal
    v-if="pendingType"
    title="更改字段类型"
    description="切换为简单类型后，当前字段的嵌套 Schema 将被删除。"
    confirm-label="更改类型"
    tone="danger"
    @close="pendingType = null"
    @confirm="confirmTypeChange"
  />
</template>
