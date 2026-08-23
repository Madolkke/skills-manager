<script setup lang="ts">
import { AlertCircle, CheckCircle2, ChevronDown, ChevronUp, Plus, RotateCcw, Save, Search, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import UiButton from "../../components/ui/UiButton.vue";
import UiIconButton from "../../components/ui/UiIconButton.vue";
import WorkflowSchemaNodeEditor from "../../features/workflow/components/WorkflowSchemaNodeEditor.vue";
import type { SystemCommand, WorkflowJsonSchema } from "../../types";
import AdminSystemCommandSchemaDialog from "./AdminSystemCommandSchemaDialog.vue";

type CommandDraft = { key: string; expression: string; enabled: boolean; metadata: Record<string, unknown>; ttp: string };
type SampleDraft = { id: string; name: string; command: string; stdout: string };
type SchemaRecord = Record<string, unknown>;

const props = defineProps<{ commands: SystemCommand[]; selectedCommandId: string }>();
const emit = defineEmits<{ select: [id: string]; create: [payload: Record<string, unknown>]; update: [id: string, payload: Record<string, unknown>]; delete: [command: SystemCommand] }>();

const search = ref("");
const statusFilter = ref<"all" | "enabled" | "disabled">("all");
const draft = ref<CommandDraft>(emptyDraft());
const samples = ref<SampleDraft[]>([]);
const schemaModel = ref<WorkflowJsonSchema>(emptySchema());
const schemaDialogOpen = ref(false);
const baseline = ref("");
const formError = ref("");
const basicInfoExpanded = ref(true);
const samplesExpanded = ref(true);
const ttpExpanded = ref(true);
const sampleExpanded = ref<Record<string, boolean>>({});
let sampleSequence = 0;

const selected = computed(() => props.commands.find((item) => item.id === props.selectedCommandId));
const isNew = computed(() => !selected.value);
const filteredCommands = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase();
  return props.commands.filter((command) => {
    if (statusFilter.value === "enabled" && command.enabled === false) return false;
    if (statusFilter.value === "disabled" && command.enabled !== false) return false;
    if (!keyword) return true;
    const metadata = command.metadata ?? {};
    return [command.key, String(command.name ?? ""), command.expression, command.description, String(metadata.device ?? ""), String(metadata.industry ?? ""), ...(Array.isArray(metadata.tags) ? metadata.tags.map(String) : [])]
      .some((value) => String(value).toLocaleLowerCase().includes(keyword));
  });
});
const sampleCount = computed(() => samples.value.length);
const schemaPropertyCount = computed(() => schemaModel.value.type === "object" ? Object.keys(schemaModel.value.properties).length : 0);
const schemaRequiredCount = computed(() => schemaModel.value.type === "object" ? schemaModel.value.required.length : 0);
const validationErrors = computed(() => validateDraft());
const dirty = computed(() => serializeDraft() !== baseline.value);
const canSave = computed(() => validationErrors.value.length === 0 && (isNew.value || dirty.value));

watch(selected, (value) => loadDraft(value), { immediate: true });

function emptyMetadata(): Record<string, unknown> {
  return { name: "", description: "", industry: "", device: "", versions: [], tags: [] };
}

function emptySchema(): WorkflowJsonSchema {
  return { type: "object", title: "", description: "", properties: {}, required: [], additionalProperties: false };
}

function emptyDraft(): CommandDraft {
  return { key: "", expression: "", enabled: true, metadata: emptyMetadata(), ttp: "" };
}

function newSample(): SampleDraft {
  sampleSequence += 1;
  return { id: `local-sample-${sampleSequence}`, name: "", command: "", stdout: "" };
}

function cloneRecord(value: unknown): SchemaRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? { ...(value as SchemaRecord) } : {};
}

function normalizeSchema(value: unknown): WorkflowJsonSchema {
  const raw = cloneRecord(value);
  const type = raw.type;
  const base = { ...raw, type, title: typeof raw.title === "string" ? raw.title : "", description: typeof raw.description === "string" ? raw.description : "" } as SchemaRecord;
  if (type === "object") {
    const properties = cloneRecord(raw.properties);
    return { ...base, type, properties: Object.fromEntries(Object.entries(properties).map(([key, child]) => [key, normalizeSchema(child)])), required: Array.isArray(raw.required) ? raw.required.filter((key): key is string => typeof key === "string") : [], additionalProperties: raw.additionalProperties === true } as WorkflowJsonSchema;
  }
  if (type === "array") return { ...base, type, items: normalizeSchema(raw.items ?? { type: "string" }) } as WorkflowJsonSchema;
  return { ...base, type } as WorkflowJsonSchema;
}

function validateSchema(value: unknown, path = "根输出 Schema"): string[] {
  const errors: string[] = [];
  const schema = cloneRecord(value);
  const type = schema.type;
  if (!["string", "integer", "number", "boolean", "object", "array"].includes(String(type))) return [`${path}必须声明受支持的 type。`];
  if (type === "object") {
    const properties = schema.properties;
    const required = schema.required;
    if (!properties || typeof properties !== "object" || Array.isArray(properties)) errors.push(`${path}必须包含 properties 对象。`);
    if (!Array.isArray(required) && path === "根输出 Schema") errors.push(`${path}必须包含 required 数组。`);
    if (schema.additionalProperties !== undefined && typeof schema.additionalProperties !== "boolean") errors.push(`${path}.additionalProperties 必须是布尔值。`);
    if (properties && typeof properties === "object" && !Array.isArray(properties)) {
      Object.entries(properties as SchemaRecord).forEach(([key, child]) => errors.push(...validateSchema(child, `${path}.${key}`)));
      if (Array.isArray(required)) {
        if (new Set(required).size !== required.length || required.some((key) => typeof key !== "string" || !(key in properties))) errors.push(`${path}.required 必须引用唯一的 properties。`);
      }
    }
  } else if (type === "array") {
    if (!("items" in schema)) errors.push(`${path}必须包含 items。`);
    else errors.push(...validateSchema(schema.items, `${path}[]`));
  }
  return errors;
}

function loadDraft(value?: SystemCommand): void {
  draft.value = value ? { key: value.key, expression: value.expression, enabled: value.enabled !== false, metadata: { ...(value.metadata ?? {}) }, ttp: value.ttp ?? "" } : emptyDraft();
  samples.value = (value?.samples ?? []).map((sample, index) => ({ id: sample.id || `saved-sample-${index + 1}`, name: sample.name, command: sample.command, stdout: sample.stdout }));
  schemaModel.value = normalizeSchema(value?.outputSchema ?? emptySchema());
  sampleExpanded.value = Object.fromEntries(samples.value.map((sample) => [sample.id, true]));
  basicInfoExpanded.value = true;
  samplesExpanded.value = true;
  ttpExpanded.value = true;
  schemaDialogOpen.value = false;
  formError.value = "";
  baseline.value = serializeDraft();
}

function serializeDraft(): string {
  return JSON.stringify({ draft: draft.value, samples: samples.value, outputSchema: schemaModel.value });
}

function confirmDiscard(): boolean {
  return !dirty.value || window.confirm("当前命令有未保存修改，继续操作会丢失这些修改。是否继续？");
}

function selectCommand(id: string): void { if (confirmDiscard()) emit("select", id); }
function newCommand(): void { if (confirmDiscard()) emit("select", ""); }
function metadataField(name: string): string { return String(draft.value.metadata[name] ?? ""); }
function metadataList(name: string): string { const value = draft.value.metadata[name]; return Array.isArray(value) ? value.map(String).join(", ") : ""; }
function setMetadata(name: string, value: unknown): void { draft.value.metadata = { ...draft.value.metadata, [name]: value }; }
function setMetadataList(name: string, value: string): void { setMetadata(name, value.split(",").map((item) => item.trim()).filter(Boolean)); }
function addSample(): void {
  const sample = newSample();
  samples.value.push(sample);
  sampleExpanded.value = { ...sampleExpanded.value, [sample.id]: true };
}
function removeSample(id: string): void { samples.value = samples.value.filter((sample) => sample.id !== id); }

function onSchemaModelChange(value: WorkflowJsonSchema): void {
  schemaModel.value = value;
}

function validateDraft(): string[] {
  const errors: string[] = [];
  if (!draft.value.key.trim()) errors.push("Key 不能为空。");
  if (!metadataField("name").trim()) errors.push("名称不能为空。");
  if (!draft.value.expression.trim()) errors.push("命令行表达式不能为空。");
  samples.value.forEach((sample, index) => {
    if (!sample.name.trim()) errors.push(`回显示例 ${index + 1} 缺少名称。`);
    if (!sample.command.trim()) errors.push(`回显示例 ${index + 1} 缺少完整命令。`);
  });
  const schemaErrors = validateSchema(schemaModel.value);
  if (schemaModel.value.type !== "object") errors.push("根输出 Schema 的 type 必须为 object。");
  errors.push(...schemaErrors);
  return Array.from(new Set(errors));
}

function sampleHasError(sample: SampleDraft): boolean {
  return !sample.name.trim() || !sample.command.trim();
}

function toggleSample(id: string): void {
  sampleExpanded.value = { ...sampleExpanded.value, [id]: !sampleExpanded.value[id] };
}

function discardChanges(): void { loadDraft(selected.value); }

function save(): void {
  formError.value = "";
  if (validationErrors.value.length) return;
  const payload = { key: draft.value.key.trim(), expression: draft.value.expression.trim(), enabled: draft.value.enabled, metadata: draft.value.metadata, ttp: draft.value.ttp, samples: samples.value.map(({ id, name, command, stdout }) => ({ id, name, command, stdout })), outputSchema: schemaModel.value };
  if (selected.value) emit("update", selected.value.id, payload);
  else emit("create", payload);
}
</script>

<template>
  <section class="admin-directory-layout admin-command-library">
    <aside class="admin-card admin-command-list">
      <div class="admin-command-list-head"><div><small>COMMAND CATALOG</small><h2>系统命令库</h2><p>{{ props.commands.length }} 条命令 · 默认供 Workflow 搜索</p></div><UiButton size="sm" variant="primary" @click="newCommand"><template #icon><Plus /></template>新建</UiButton></div>
      <label class="admin-command-search"><Search :size="15" /><input v-model="search" type="search" placeholder="搜索 Key、名称或命令表达式" /></label>
      <div class="admin-command-filters" role="tablist" aria-label="命令状态筛选"><button v-for="option in [{ id: 'all', label: '全部' }, { id: 'enabled', label: '已启用' }, { id: 'disabled', label: '已停用' }]" :key="option.id" type="button" :class="statusFilter === option.id && 'active'" role="tab" :aria-selected="statusFilter === option.id" @click="statusFilter = option.id as typeof statusFilter">{{ option.label }}</button></div>
      <div class="admin-command-list-scroll">
        <button v-for="command in filteredCommands" :key="command.id" type="button" :class="['admin-directory-item', command.id === props.selectedCommandId && 'active']" @click="selectCommand(command.id)"><span class="admin-command-item-title"><strong>{{ command.metadata?.name || command.name || command.key }}</strong><i :class="command.enabled !== false ? 'is-enabled' : 'is-disabled'">{{ command.enabled !== false ? "启用" : "停用" }}</i></span><code>{{ command.expression }}</code><small>{{ command.key }}<template v-if="command.metadata?.device"> · {{ command.metadata.device }}</template></small></button>
        <div v-if="!filteredCommands.length" class="admin-command-empty"><Search :size="22" /><strong>{{ props.commands.length ? "没有匹配的命令" : "还没有系统命令" }}</strong><span>{{ props.commands.length ? "调整搜索词或状态筛选。" : "创建第一条系统命令开始测试。" }}</span></div>
      </div>
    </aside>

    <section class="admin-card admin-command-editor">
      <template v-if="isNew || selected">
        <header class="admin-command-editor-head"><div><small>SYSTEM SOURCE</small><h2>{{ isNew ? "新建系统命令" : "编辑系统命令" }}<span v-if="dirty" class="admin-unsaved-dot">未保存</span></h2><p>{{ isNew ? "填写命令表达式和输出契约，保存后即可在 Workflow 中搜索。" : selected?.expression }}</p></div><UiIconButton v-if="selected" label="删除系统命令" variant="danger" @click="emit('delete', selected)"><Trash2 /></UiIconButton></header>
        <div class="admin-command-editor-scroll">
          <section class="admin-command-section" :class="!basicInfoExpanded && 'is-collapsed'"><div class="admin-command-section-head"><div><h3>基本信息</h3><p>{{ metadataField('name') || "未命名命令" }} · {{ draft.expression || "尚未填写命令表达式" }}</p></div><div class="admin-command-section-actions"><label class="admin-command-switch"><input v-model="draft.enabled" type="checkbox" /><span>启用命令</span></label><button type="button" class="admin-command-collapse" :aria-expanded="basicInfoExpanded" aria-controls="admin-command-basic-info" @click="basicInfoExpanded = !basicInfoExpanded"><ChevronUp v-if="basicInfoExpanded" :size="16" /><ChevronDown v-else :size="16" /><span>{{ basicInfoExpanded ? "收起" : "展开" }}</span></button></div></div><div v-show="basicInfoExpanded" id="admin-command-basic-info" class="admin-command-section-body"><div class="admin-command-field-grid"><label class="field-label"><span>Key <b>*</b></span><input v-model="draft.key" placeholder="show_system_status" /></label><label class="field-label"><span>名称 <b>*</b></span><input :value="metadataField('name')" placeholder="系统状态" @input="setMetadata('name', ($event.target as HTMLInputElement).value)" /></label><label class="field-label span-2"><span>命令行表达式 <b>*</b></span><input v-model="draft.expression" class="admin-command-expression" placeholder="show interface <interface>" /><small class="field-help">支持关键字、&lt;参数&gt;、可选组和选项组；保存时由后端规范化和校验。</small></label><label class="field-label span-2"><span>说明</span><textarea :value="metadataField('description')" rows="2" placeholder="这条命令采集什么信息？" @input="setMetadata('description', ($event.target as HTMLTextAreaElement).value)" /></label><label class="field-label"><span>设备</span><input :value="metadataField('device')" placeholder="网络设备" @input="setMetadata('device', ($event.target as HTMLInputElement).value)" /></label><label class="field-label"><span>行业</span><input :value="metadataField('industry')" placeholder="通用" @input="setMetadata('industry', ($event.target as HTMLInputElement).value)" /></label><label class="field-label"><span>适用版本</span><input :value="metadataList('versions')" placeholder="留空表示全版本" @input="setMetadataList('versions', ($event.target as HTMLInputElement).value)" /></label><label class="field-label"><span>标签</span><input :value="metadataList('tags')" placeholder="network, status" @input="setMetadataList('tags', ($event.target as HTMLInputElement).value)" /></label></div></div></section>

          <section class="admin-command-section" :class="!samplesExpanded && 'is-collapsed'"><div class="admin-command-section-head"><div><h3>回显示例</h3><p>{{ sampleCount }} 个实例 · 实际命令与完整 stdout</p></div><div class="admin-command-section-actions"><span class="admin-command-counter">{{ sampleCount }} 个</span><UiButton aria-label="添加回显示例" size="sm" variant="secondary" @click="addSample"><template #icon><Plus /></template>添加示例</UiButton><button type="button" class="admin-command-collapse" :aria-expanded="samplesExpanded" aria-controls="admin-command-samples" @click="samplesExpanded = !samplesExpanded"><ChevronUp v-if="samplesExpanded" :size="16" /><ChevronDown v-else :size="16" /><span>{{ samplesExpanded ? "收起" : "展开" }}</span></button></div></div><div v-show="samplesExpanded" id="admin-command-samples" class="admin-command-section-body"><div class="admin-command-samples"><article v-for="(sample, index) in samples" :key="sample.id" class="admin-command-sample" :class="[!sampleExpanded[sample.id] && 'is-collapsed', sampleHasError(sample) && 'has-error']"><header><button type="button" class="admin-command-sample-toggle" :aria-expanded="sampleExpanded[sample.id] !== false" :aria-label="`${sampleExpanded[sample.id] !== false ? '收起' : '展开'}回显示例 ${index + 1}`" @click="toggleSample(sample.id)"><ChevronUp v-if="sampleExpanded[sample.id] !== false" :size="15" /><ChevronDown v-else :size="15" /><strong>示例 {{ index + 1 }}</strong><span>{{ sample.name || "未命名" }} · {{ sample.command || "未填写命令" }} · stdout {{ sample.stdout.length }} 字符</span></button><UiIconButton label="删除回显示例" size="sm" variant="danger" @click="removeSample(sample.id)"><Trash2 /></UiIconButton></header><div v-show="sampleExpanded[sample.id] !== false" class="admin-command-sample-body"><label class="field-label"><span>示例名称 <b>*</b></span><input v-model="sample.name" placeholder="正常状态" /></label><label class="field-label"><span>实际触发命令 <b>*</b></span><input v-model="sample.command" class="admin-command-mono" placeholder="show status" /></label><label class="field-label"><span>stdout</span><textarea v-model="sample.stdout" class="admin-command-mono" rows="7" spellcheck="false" placeholder="粘贴完整回显内容" /></label></div></article><div v-if="!samples.length" class="admin-command-inline-empty">暂无回显示例，点击“添加示例”创建第一条。</div></div></div></section>

          <section class="admin-command-section admin-command-schema-section"><div class="admin-command-section-head"><div><h3>输出 Schema</h3><p>{{ schemaPropertyCount }} 个根字段 · {{ schemaRequiredCount }} 个必填 · 结构化编辑</p></div><UiButton size="sm" variant="secondary" @click="schemaDialogOpen = true">编辑原始 JSON Schema</UiButton></div><div class="admin-command-schema-compact"><WorkflowSchemaNodeEditor :schema="schemaModel" :readonly="false" :show-required="true" :show-additional-properties="true" @change="onSchemaModelChange" /></div></section>

          <section class="admin-command-section admin-command-ttp-section" :class="!ttpExpanded && 'is-collapsed'"><div class="admin-command-section-head"><div><h3>TTP 原文</h3><p>仅保存原文，不参与当前版本的解析。{{ draft.ttp ? ` · ${draft.ttp.length} 字符` : " · 尚未填写" }}</p></div><button type="button" class="admin-command-collapse" :aria-expanded="ttpExpanded" aria-controls="admin-command-ttp" @click="ttpExpanded = !ttpExpanded"><ChevronUp v-if="ttpExpanded" :size="16" /><ChevronDown v-else :size="16" /><span>{{ ttpExpanded ? "收起" : "展开" }}</span></button></div><div v-show="ttpExpanded" id="admin-command-ttp" class="admin-command-section-body"><textarea v-model="draft.ttp" rows="9" class="admin-command-mono admin-command-ttp" spellcheck="false" placeholder="可粘贴 TTP、厂商文档片段或审阅备注。" /></div></section>
          <div v-if="validationErrors.length || formError" class="admin-command-validation" role="alert"><AlertCircle :size="17" /><div><strong>保存前需要处理以下问题</strong><p v-if="formError">{{ formError }}</p><p v-for="error in validationErrors" :key="error">{{ error }}</p></div></div><div v-else class="admin-command-valid"><CheckCircle2 :size="17" /><span>{{ dirty ? "内容已准备好，可以保存。" : "当前内容已保存。" }}</span></div>
        </div>
        <footer class="admin-command-editor-foot"><UiButton variant="secondary" :disabled="!dirty" @click="discardChanges"><template #icon><RotateCcw /></template>撤销修改</UiButton><UiButton variant="primary" :disabled="!canSave" @click="save"><template #icon><Save /></template>{{ isNew ? "创建系统命令" : "保存修改" }}</UiButton></footer>
        <AdminSystemCommandSchemaDialog :open="schemaDialogOpen" :schema="schemaModel" :normalize="normalizeSchema" :validate="validateSchema" @close="schemaDialogOpen = false" @confirm="schemaModel = $event; schemaDialogOpen = false" />
      </template>
    </section>
  </section>
</template>
