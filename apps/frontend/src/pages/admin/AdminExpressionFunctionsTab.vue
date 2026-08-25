<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Plus, Save, Trash2, Undo2 } from "lucide-vue-next";
import UiButton from "../../components/ui/UiButton.vue";
import UiIconButton from "../../components/ui/UiIconButton.vue";
import WorkflowSchemaNodeEditor from "../../features/workflow/components/WorkflowSchemaNodeEditor.vue";
import AdminSystemCommandSchemaDialog from "./AdminSystemCommandSchemaDialog.vue";
import type { ExpressionFunction, ExpressionFunctionPayload, WorkflowJsonSchema } from "../../types";
import { newWorkflowSchema } from "../../features/workflow/workflowJsonSchema";
import { isWorkflowExpressionIdentifier } from "../../features/workflow/workflowExpressionSyntax";

const props = defineProps<{ functions: ExpressionFunction[]; selectedFunctionId: string }>();
const emit = defineEmits<{ select: [id: string]; create: [payload: ExpressionFunctionPayload]; update: [id: string, payload: ExpressionFunctionPayload]; delete: [item: ExpressionFunction] }>();
const search = ref("");
const draft = ref<ExpressionFunctionPayload>(newDraft());
const saved = ref("");
const parameterDialogOpen = ref(false);
const returnDialogOpen = ref(false);
const parameterSchema = ref<WorkflowJsonSchema>(newWorkflowSchema("object"));
const returnSchema = ref<WorkflowJsonSchema>(newWorkflowSchema("string"));

const selected = computed(() => props.functions.find((item) => item.id === props.selectedFunctionId));
const filtered = computed(() => props.functions.filter((item) => `${item.name} ${item.description} ${item.isBuiltin ? "内置" : "自定义"}`.toLowerCase().includes(search.value.trim().toLowerCase())));
const dirty = computed(() => JSON.stringify(draft.value) !== saved.value);
const schemaErrors = computed(() => [...validateSchema(parameterSchema.value, true), ...validateSchema(returnSchema.value, false)]);
const canSave = computed(() => Boolean(draft.value.name.trim() && draft.value.body.trim() && draft.value.body.length <= 50000 && !schemaErrors.value.length && isWorkflowExpressionIdentifier(draft.value.name) && !draft.value.name.startsWith("_")));

watch(() => [props.selectedFunctionId, selected.value] as const, () => loadDraft(selected.value));

function newDraft(): ExpressionFunctionPayload {
  return { name: "new_function", description: "", parameterSchema: newWorkflowSchema("object"), returnSchema: newWorkflowSchema("string"), body: "# Describe the function body here", language: "python", isBuiltin: false, enabled: true };
}
function loadDraft(item?: ExpressionFunction): void {
  const value = item ? { ...item } : newDraft();
  draft.value = { id: value.id, name: value.name, description: value.description, parameterSchema: value.parameterSchema, returnSchema: value.returnSchema, body: value.body, language: value.language, isBuiltin: value.isBuiltin, enabled: value.enabled };
  parameterSchema.value = value.parameterSchema;
  returnSchema.value = value.returnSchema;
  saved.value = JSON.stringify(draft.value);
}
function create(): void { emit("create", newDraft()); }
function save(): void {
  if (!canSave.value) return;
  const payload = { ...draft.value, parameterSchema: normalizeForSave(parameterSchema.value), returnSchema: normalizeForSave(returnSchema.value) };
  draft.value = payload;
  if (payload.id) emit("update", payload.id, payload);
  else emit("create", payload);
  saved.value = JSON.stringify(payload);
}
function normalizeSchema(value: unknown): WorkflowJsonSchema {
  if (!value || typeof value !== "object") return newWorkflowSchema("string");
  const source = value as Record<string, any>;
  const type = source.type;
  if (type === "object") return { type, title: String(source.title || ""), description: String(source.description || ""), properties: Object.fromEntries(Object.entries(source.properties || {}).map(([key, child]) => [key, normalizeSchema(child)])), required: Array.isArray(source.required) ? source.required : [], additionalProperties: source.additionalProperties !== false };
  if (type === "array") return { type, title: String(source.title || ""), description: String(source.description || ""), items: normalizeSchema(source.items) };
  if (["string", "integer", "number", "boolean"].includes(type)) return { type, title: String(source.title || ""), description: String(source.description || "") } as WorkflowJsonSchema;
  return newWorkflowSchema("string");
}
function normalizeForSave(value: WorkflowJsonSchema): WorkflowJsonSchema {
  if (value.type === "object") {
    return { ...value, properties: Object.fromEntries(Object.entries(value.properties).sort(([left], [right]) => left.localeCompare(right)).map(([key, child]) => [key, normalizeForSave(child)])), required: [...value.required] };
  }
  if (value.type === "array") return { ...value, items: normalizeForSave(value.items) };
  return { ...value };
}
function validateSchema(value: WorkflowJsonSchema, rootObject: boolean): string[] {
  const errors: string[] = [];
  if (rootObject && value.type !== "object") errors.push("参数 Schema 根节点必须是 object。");
  function visit(node: WorkflowJsonSchema): void {
    if (!node.type) { errors.push("Schema 节点必须声明 type。"); return; }
    if (node.type === "object") {
      const required = node.required ?? [];
      if (!node.properties || !Array.isArray(required) || new Set(required).size !== required.length || required.some((key) => !(key in node.properties))) errors.push("Schema 结构不完整或 required 引用了不存在的属性。");
      if (node.additionalProperties !== undefined && typeof node.additionalProperties !== "boolean") errors.push("additionalProperties 必须是布尔值。");
      for (const key of Object.keys(node.properties ?? {})) { if (rootObject && (!isWorkflowExpressionIdentifier(key) || key.startsWith("_"))) errors.push(`参数名“${key}”必须是合法标识符。`); visit(node.properties[key]); }
    }
    else if (node.type === "array") visit(node.items);
  }
  visit(value);
  return [...new Set(errors)];
}
function updateSchema(kind: "parameter" | "return", value: WorkflowJsonSchema): void {
  if (kind === "parameter") parameterSchema.value = value;
  else returnSchema.value = value;
}
</script>

<template>
  <div class="admin-expression-functions">
    <aside class="admin-expression-function-list">
      <div class="admin-expression-list-head"><input v-model="search" aria-label="搜索表达式函数" placeholder="搜索函数..." /><UiButton size="sm" variant="secondary" @click="create"><template #icon><Plus /></template>新建</UiButton></div>
      <button v-for="item in filtered" :key="item.id" type="button" :class="['admin-expression-function-item', { active: item.id === props.selectedFunctionId }]" @click="emit('select', item.id)"><strong>{{ item.name }}</strong><span>{{ item.isBuiltin ? "内置" : "自定义" }} · {{ item.enabled ? "启用" : "停用" }}</span></button>
      <p v-if="!filtered.length" class="empty-state">暂无表达式函数。</p>
    </aside>
    <section class="admin-expression-function-editor">
      <template v-if="draft">
        <div class="admin-expression-editor-head"><div><h2>{{ draft.name || "新建表达式函数" }}</h2><p>函数体仅作为文本保存，不会执行。</p></div><div class="admin-expression-editor-actions"><UiButton size="sm" variant="secondary" :disabled="!dirty" @click="loadDraft(selected)"><template #icon><Undo2 /></template>撤销</UiButton><UiButton size="sm" variant="primary" :disabled="!canSave" @click="save"><template #icon><Save /></template>保存</UiButton><UiIconButton v-if="selected" label="删除函数" tone="danger" @click="emit('delete', selected!)"><Trash2 /></UiIconButton></div></div>
        <div class="admin-expression-fields"><label>函数名<input v-model="draft.name" /><small v-if="draft.name && (!isWorkflowExpressionIdentifier(draft.name) || draft.name.startsWith('_'))">必须是合法 Python 标识符，且不能以下划线开头。</small></label><label>说明<textarea v-model="draft.description" rows="2" /></label><label class="admin-expression-switch"><input v-model="draft.enabled" type="checkbox" />启用</label><label>语言<input v-model="draft.language" /></label></div>
        <div class="admin-expression-schema-grid"><section><div class="admin-expression-section-head"><h3>参数 Schema</h3><UiButton size="sm" variant="secondary" @click="parameterDialogOpen = true">编辑 JSON</UiButton></div><WorkflowSchemaNodeEditor :schema="parameterSchema" :readonly="false" :show-metadata="false" :show-required="true" :show-additional-properties="true" identifier-only @change="updateSchema('parameter', $event)" /><p v-if="schemaErrors.length" class="admin-expression-error">{{ schemaErrors[0] }}</p></section><section><div class="admin-expression-section-head"><h3>返回 Schema</h3><UiButton size="sm" variant="secondary" @click="returnDialogOpen = true">编辑 JSON</UiButton></div><WorkflowSchemaNodeEditor :schema="returnSchema" :readonly="false" :show-metadata="false" :show-required="true" :show-additional-properties="true" @change="updateSchema('return', $event)" /></section></div>
        <label class="admin-expression-body">函数体<textarea v-model="draft.body" spellcheck="false" rows="12" /><small>{{ draft.body.length }} / 50000 字符；仅保存文本，不会执行。</small></label>
      </template>
    </section>
    <AdminSystemCommandSchemaDialog :open="parameterDialogOpen" :schema="parameterSchema" :normalize="normalizeSchema" :validate="(value) => validateSchema(normalizeSchema(value), true)" title="编辑参数 JSON Schema" description="参数根节点必须是 object；属性名必须是合法标识符。" @close="parameterDialogOpen = false" @confirm="updateSchema('parameter', $event); parameterDialogOpen = false" />
    <AdminSystemCommandSchemaDialog :open="returnDialogOpen" :schema="returnSchema" :normalize="normalizeSchema" :validate="(value) => validateSchema(normalizeSchema(value), false)" title="编辑返回值 JSON Schema" description="返回 Schema 支持标量、object 和 array。" @close="returnDialogOpen = false" @confirm="updateSchema('return', $event); returnDialogOpen = false" />
  </div>
</template>

<style scoped>
.admin-expression-functions { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 18px; min-height: 620px; }
.admin-expression-function-list { border-right: 1px solid var(--border-subtle); padding-right: 14px; }
.admin-expression-list-head, .admin-expression-editor-head, .admin-expression-section-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.admin-expression-list-head input, .admin-expression-fields input, .admin-expression-fields textarea, .admin-expression-body textarea { width: 100%; border: 1px solid var(--border-subtle); background: var(--surface); padding: 8px; }
.admin-expression-function-item { display: grid; width: 100%; text-align: left; gap: 3px; border: 0; border-bottom: 1px solid var(--border-subtle); background: transparent; padding: 11px 8px; cursor: pointer; }
.admin-expression-function-item.active { background: var(--surface-muted); }
.admin-expression-function-item span, small { color: var(--text-muted); font-size: 12px; }
.admin-expression-fields { display: grid; grid-template-columns: 1fr 2fr 100px 120px; gap: 12px; align-items: start; }
.admin-expression-fields label, .admin-expression-body { display: grid; gap: 6px; font-weight: 600; }
.admin-expression-switch { display: flex !important; align-items: center; margin-top: 30px; }
.admin-expression-switch input { width: auto; }
.admin-expression-schema-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
.admin-expression-section-head { margin-bottom: 8px; }
.admin-expression-section-head h3 { margin: 0; font-size: 14px; }
.admin-expression-body { margin-top: 16px; }
.admin-expression-body textarea { font-family: var(--mono-font); resize: vertical; }
.admin-expression-error { color: var(--danger); }
.admin-expression-editor-actions { display: flex; align-items: center; gap: 8px; }
@media (max-width: 900px) { .admin-expression-functions, .admin-expression-schema-grid, .admin-expression-fields { grid-template-columns: 1fr; } .admin-expression-function-list { border-right: 0; border-bottom: 1px solid var(--border-subtle); padding: 0 0 14px; } .admin-expression-switch { margin-top: 0; } }
</style>
