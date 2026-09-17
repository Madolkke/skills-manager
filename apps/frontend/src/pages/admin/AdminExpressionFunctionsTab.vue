<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Plus, Save, Trash2, Undo2 } from "lucide-vue-next";
import UiButton from "../../components/ui/UiButton.vue";
import UiIconButton from "../../components/ui/UiIconButton.vue";
import Modal from "../../components/Modal.vue";
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
const deleteTarget = ref<ExpressionFunction | null>(null);
const parameterSchema = ref<WorkflowJsonSchema>(newWorkflowSchema("object"));
const returnSchema = ref<WorkflowJsonSchema>(newWorkflowSchema("string"));

const selected = computed(() => props.functions.find((item) => item.id === props.selectedFunctionId));
const filtered = computed(() => props.functions.filter((item) => `${item.name} ${item.description} ${item.isBuiltin ? "内置" : "自定义"}`.toLowerCase().includes(search.value.trim().toLowerCase())));
const dirty = computed(() => JSON.stringify({ ...draft.value, parameterSchema: parameterSchema.value, returnSchema: returnSchema.value }) !== saved.value);
const schemaErrors = computed(() => [...validateSchema(parameterSchema.value, true), ...validateSchema(returnSchema.value, false)]);
const canSave = computed(() => Boolean(draft.value.name.trim() && draft.value.body.trim() && draft.value.body.length <= 50000 && !schemaErrors.value.length && isWorkflowExpressionIdentifier(draft.value.name) && !draft.value.name.startsWith("_") && draft.value.name.length <= 120 && draft.value.description.length <= 2000 && draft.value.language.trim() && draft.value.language.length <= 40));

watch(() => [props.selectedFunctionId, selected.value] as const, () => loadDraft(selected.value), { immediate: true });

function newDraft(): ExpressionFunctionPayload {
  return { name: "new_function", description: "", parameterSchema: newWorkflowSchema("object"), returnSchema: newWorkflowSchema("string"), body: "# Describe the function body here", language: "python", isBuiltin: false, enabled: true };
}
function loadDraft(item?: ExpressionFunction): void {
  const value = item ? JSON.parse(JSON.stringify(item)) : newDraft();
  draft.value = { id: value.id, name: value.name, description: value.description, parameterSchema: value.parameterSchema, returnSchema: value.returnSchema, body: value.body, language: value.language, isBuiltin: value.isBuiltin, enabled: value.enabled };
  parameterSchema.value = value.parameterSchema;
  returnSchema.value = value.returnSchema;
  saved.value = JSON.stringify(draft.value);
}
function create(): void { emit("select", ""); loadDraft(); }
function save(): void {
  if (!canSave.value) return;
  const payload = { ...draft.value, parameterSchema: normalizeForSave(parameterSchema.value), returnSchema: normalizeForSave(returnSchema.value) };
  draft.value = payload;
  if (payload.id) emit("update", payload.id, payload);
  else emit("create", payload);

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
    return Object.assign({ ...value, properties: Object.fromEntries(Object.entries(value.properties).map(([key, child]) => [key, normalizeForSave(child)])), required: [...value.required] }, { "x-parameter-order": Object.keys(value.properties) });
  }
  if (value.type === "array") return { ...value, items: normalizeForSave(value.items) };
  return { ...value };
}
function validateSchema(value: unknown, rootObject: boolean): string[] {
  const errors: string[] = [];
  function visit(raw: unknown, parameters = false): void {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) { errors.push("Schema 必须是对象。"); return; }
    const node = raw as Record<string, any>;
    if (parameters && node.type !== "object") errors.push("参数 Schema 根节点必须是 object。");
    if (!["object", "array", "string", "integer", "number", "boolean"].includes(node.type)) errors.push("Schema 节点类型无效。");
    if (node.type === "object") {
      if (!node.properties || typeof node.properties !== "object" || Array.isArray(node.properties)) { errors.push("object 必须声明 properties。"); return; }
      const required = node.required ?? [];
      if (!Array.isArray(required) || new Set(required).size !== required.length || required.some((key: unknown) => typeof key !== "string" || !(key in node.properties))) errors.push("required 必须引用不重复的属性名。");
      if (node.additionalProperties !== undefined && typeof node.additionalProperties !== "boolean") errors.push("additionalProperties 必须是布尔值。");
      for (const [key, child] of Object.entries(node.properties)) {
        if (parameters && (!isWorkflowExpressionIdentifier(key) || key.startsWith("_"))) errors.push(`参数名“${key}”必须是合法标识符。`);
        visit(child);
      }
    } else if (node.type === "array") visit(node.items);
  }
  visit(value, rootObject);
  return [...new Set(errors)];
}

function updateSchema(kind: "parameter" | "return", value: WorkflowJsonSchema): void {
  if (kind === "parameter") parameterSchema.value = value;
  else returnSchema.value = value;
}
</script>

<template>
  <div class="admin-expression-functions">
    <aside class="admin-card admin-expression-function-list">
      <header class="admin-expression-list-title"><small>FUNCTION CATALOG</small><h2>表达式函数库</h2><p>{{ props.functions.length }} 个函数 · 静态声明</p></header>
      <div class="admin-expression-list-head"><input v-model="search" aria-label="搜索表达式函数" placeholder="搜索函数..." /><UiButton size="sm" variant="secondary" @click="create"><template #icon><Plus /></template>新建</UiButton></div>
      <div class="admin-expression-list-scroll">
        <button v-for="item in filtered" :key="item.id" type="button" :class="['admin-expression-function-item', { active: item.id === props.selectedFunctionId }]" :aria-pressed="item.id === props.selectedFunctionId" @click="emit('select', item.id)"><strong>{{ item.name }}</strong><span>{{ item.isBuiltin ? "内置" : "自定义" }} · {{ item.enabled ? "启用" : "停用" }}</span></button>
        <p v-if="!filtered.length" class="empty-state">{{ search.trim() ? "没有匹配的函数，请调整搜索条件。" : "暂无表达式函数，点击新建添加。" }}</p>
      </div>
    </aside>
    <section class="admin-card admin-expression-function-editor">
      <template v-if="draft">
        <div class="admin-expression-editor-head"><div><h2>{{ draft.name || "新建表达式函数" }}</h2><p>函数体仅作为文本保存，不会执行。</p><span class="admin-expression-save-state" role="status">{{ !draft.id ? "新建草稿" : dirty ? "有未保存修改" : "内容已保存" }}</span></div><div class="admin-expression-editor-actions"><UiButton size="sm" variant="secondary" :disabled="!dirty" @click="loadDraft(selected)"><template #icon><Undo2 /></template>撤销</UiButton><UiButton size="sm" variant="primary" :disabled="!canSave" @click="save"><template #icon><Save /></template>保存</UiButton><UiIconButton v-if="selected && draft.id" label="删除函数" variant="danger" @click="deleteTarget = selected!"><Trash2 /></UiIconButton></div></div>
        <div class="admin-expression-editor-scroll">
          <div class="admin-expression-fields"><label>函数名<input v-model="draft.name" /><small v-if="draft.name && (!isWorkflowExpressionIdentifier(draft.name) || draft.name.startsWith('_'))">必须是合法 Python 标识符，且不能以下划线开头。</small></label><label>说明<textarea v-model="draft.description" rows="2" /></label><label class="admin-expression-switch"><input v-model="draft.enabled" type="checkbox" />启用</label><label>语言<input v-model="draft.language" /></label></div>
          <div class="admin-expression-schema-grid"><section><div class="admin-expression-section-head"><h3>参数 Schema</h3><UiButton size="sm" variant="secondary" @click="parameterDialogOpen = true">编辑 JSON</UiButton></div><WorkflowSchemaNodeEditor :schema="parameterSchema" :readonly="false" :show-metadata="false" :show-required="true" :show-additional-properties="true" identifier-only @change="updateSchema('parameter', $event)" /><p v-if="schemaErrors.length" class="admin-expression-error" role="alert">{{ schemaErrors[0] }}</p></section><section><div class="admin-expression-section-head"><h3>返回 Schema</h3><UiButton size="sm" variant="secondary" @click="returnDialogOpen = true">编辑 JSON</UiButton></div><WorkflowSchemaNodeEditor :schema="returnSchema" :readonly="false" :show-metadata="false" :show-required="true" :show-additional-properties="true" @change="updateSchema('return', $event)" /></section></div>
          <label class="admin-expression-body">函数体<textarea v-model="draft.body" spellcheck="false" rows="12" /><small>{{ draft.body.length }} / 50000 字符；仅保存文本，不会执行。</small></label>
        </div>
      </template>
    </section>
    <Modal :open="Boolean(deleteTarget)" title="删除表达式函数" description="已有 Workflow 调用会在后续校验中报告未注册函数。" @close="deleteTarget = null">
      <div class="form-stack">
        <p>确认删除“{{ deleteTarget?.name }}”？</p>
        <div class="modal-actions"><UiButton variant="secondary" @click="deleteTarget = null">取消</UiButton><UiButton variant="danger" @click="emit('delete', deleteTarget!); deleteTarget = null">确认删除</UiButton></div>
      </div>
    </Modal>
    <AdminSystemCommandSchemaDialog :open="parameterDialogOpen" :schema="parameterSchema" :normalize="normalizeSchema" :validate="(value) => validateSchema(value, true)" title="编辑参数 JSON Schema" description="参数根节点必须是 object；属性名必须是合法标识符。" @close="parameterDialogOpen = false" @confirm="updateSchema('parameter', $event); parameterDialogOpen = false" />
    <AdminSystemCommandSchemaDialog :open="returnDialogOpen" :schema="returnSchema" :normalize="normalizeSchema" :validate="(value) => validateSchema(value, false)" title="编辑返回值 JSON Schema" description="返回 Schema 支持标量、object 和 array。" @close="returnDialogOpen = false" @confirm="updateSchema('return', $event); returnDialogOpen = false" />
  </div>
</template>
