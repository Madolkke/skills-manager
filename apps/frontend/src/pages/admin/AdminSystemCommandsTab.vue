<script setup lang="ts">
import { AlertCircle, Braces, CheckCircle2, Plus, RotateCcw, Save, Search, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import UiButton from "../../components/ui/UiButton.vue";
import UiIconButton from "../../components/ui/UiIconButton.vue";
import type { SystemCommand } from "../../types";

type CommandDraft = {
  key: string;
  expression: string;
  enabled: boolean;
  metadata: Record<string, unknown>;
  ttp: string;
};

type JsonEditor = "samples" | "schema";

const props = defineProps<{ commands: SystemCommand[]; selectedCommandId: string }>();
const emit = defineEmits<{
  select: [id: string];
  create: [payload: Record<string, unknown>];
  update: [id: string, payload: Record<string, unknown>];
  delete: [command: SystemCommand];
}>();

const search = ref("");
const statusFilter = ref<"all" | "enabled" | "disabled">("all");
const draft = ref<CommandDraft>(emptyDraft());
const jsonSamples = ref("[]");
const jsonSchema = ref(JSON.stringify(emptySchema(), null, 2));
const baseline = ref("");
const formError = ref("");

const selected = computed(() => props.commands.find((item) => item.id === props.selectedCommandId));
const isNew = computed(() => !selected.value);
const filteredCommands = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase();
  return props.commands.filter((command) => {
    if (statusFilter.value === "enabled" && command.enabled === false) return false;
    if (statusFilter.value === "disabled" && command.enabled !== false) return false;
    if (!keyword) return true;
    const metadata = command.metadata ?? {};
    return [
      command.key,
      String(command.name ?? ""),
      command.expression,
      command.description,
      String(metadata.device ?? ""),
      String(metadata.industry ?? ""),
      ...(Array.isArray(metadata.tags) ? metadata.tags.map(String) : []),
    ].some((value) => String(value).toLocaleLowerCase().includes(keyword));
  });
});
const sampleCount = computed(() => parsedArray(jsonSamples.value)?.length ?? 0);
const schemaPropertyCount = computed(() => {
  const value = parsedObject(jsonSchema.value);
  return value && typeof value.properties === "object" && value.properties !== null
    ? Object.keys(value.properties).length
    : 0;
});
const validationErrors = computed(() => validateDraft());
const dirty = computed(() => serializeDraft() !== baseline.value);
const canSave = computed(() => validationErrors.value.length === 0 && (isNew.value || dirty.value));

watch(selected, (value) => loadDraft(value), { immediate: true });

function emptyMetadata(): Record<string, unknown> {
  return { name: "", description: "", industry: "", device: "", versions: [], tags: [] };
}

function emptySchema(): Record<string, unknown> {
  return { type: "object", properties: {}, required: [], additionalProperties: false };
}

function emptyDraft(): CommandDraft {
  return { key: "", expression: "", enabled: true, metadata: emptyMetadata(), ttp: "" };
}

function loadDraft(value?: SystemCommand): void {
  draft.value = value
    ? {
        key: value.key,
        expression: value.expression,
        enabled: value.enabled !== false,
        metadata: { ...(value.metadata ?? {}) },
        ttp: value.ttp ?? "",
      }
    : emptyDraft();
  jsonSamples.value = JSON.stringify(value?.samples ?? [], null, 2);
  jsonSchema.value = JSON.stringify(value?.outputSchema ?? emptySchema(), null, 2);
  formError.value = "";
  baseline.value = serializeDraft();
}

function serializeDraft(): string {
  return JSON.stringify({ draft: draft.value, jsonSamples: jsonSamples.value, jsonSchema: jsonSchema.value });
}

function confirmDiscard(): boolean {
  return !dirty.value || window.confirm("当前命令有未保存修改，继续操作会丢失这些修改。是否继续？");
}

function selectCommand(id: string): void {
  if (!confirmDiscard()) return;
  emit("select", id);
}

function newCommand(): void {
  if (!confirmDiscard()) return;
  emit("select", "");
}

function metadataField(name: string): string {
  return String(draft.value.metadata[name] ?? "");
}

function metadataList(name: string): string {
  const value = draft.value.metadata[name];
  return Array.isArray(value) ? value.map(String).join(", ") : "";
}

function setMetadata(name: string, value: unknown): void {
  draft.value.metadata = { ...draft.value.metadata, [name]: value };
}

function setMetadataList(name: string, value: string): void {
  setMetadata(name, value.split(",").map((item) => item.trim()).filter(Boolean));
}

function parsedArray(value: string): unknown[] | null {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function parsedObject(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function validateDraft(): string[] {
  const errors: string[] = [];
  if (!draft.value.key.trim()) errors.push("Key 不能为空。");
  if (!metadataField("name").trim()) errors.push("名称不能为空。");
  if (!draft.value.expression.trim()) errors.push("命令行表达式不能为空。");
  const samples = parsedArray(jsonSamples.value);
  if (!samples) errors.push("回显示例必须是 JSON 数组。");
  else samples.forEach((sample, index) => {
    if (!sample || typeof sample !== "object" || Array.isArray(sample)) errors.push(`回显示例 ${index + 1} 必须是对象。`);
    else {
      const item = sample as Record<string, unknown>;
      if (!String(item.name ?? "").trim()) errors.push(`回显示例 ${index + 1} 缺少名称。`);
      if (!String(item.command ?? "").trim()) errors.push(`回显示例 ${index + 1} 缺少完整命令。`);
      if (typeof item.stdout !== "string") errors.push(`回显示例 ${index + 1} 的 stdout 必须是文本。`);
    }
  });
  const schema = parsedObject(jsonSchema.value);
  if (!schema) errors.push("根输出 Schema 必须是 JSON 对象。");
  else {
    if (schema.type !== "object") errors.push("根输出 Schema 的 type 必须为 object。");
    if (!schema.properties || typeof schema.properties !== "object" || Array.isArray(schema.properties)) errors.push("根输出 Schema 必须包含 properties 对象。");
    if (!Array.isArray(schema.required)) errors.push("根输出 Schema 必须包含 required 数组。");
  }
  return errors;
}

function formatJson(editor: JsonEditor): void {
  const source = editor === "samples" ? jsonSamples.value : jsonSchema.value;
  try {
    const formatted = JSON.stringify(JSON.parse(source), null, 2);
    if (editor === "samples") jsonSamples.value = formatted;
    else jsonSchema.value = formatted;
    formError.value = "";
  } catch {
    formError.value = editor === "samples" ? "回显示例 JSON 无法格式化。" : "输出 Schema JSON 无法格式化。";
  }
}

function discardChanges(): void {
  loadDraft(selected.value);
}

function save(): void {
  formError.value = "";
  if (validationErrors.value.length) return;
  const payload = {
    key: draft.value.key.trim(),
    expression: draft.value.expression.trim(),
    enabled: draft.value.enabled,
    metadata: draft.value.metadata,
    ttp: draft.value.ttp,
    samples: JSON.parse(jsonSamples.value),
    outputSchema: JSON.parse(jsonSchema.value),
  };
  if (selected.value) emit("update", selected.value.id, payload);
  else emit("create", payload);
}
</script>

<template>
  <section class="admin-directory-layout admin-command-library">
    <aside class="admin-card admin-command-list">
      <div class="admin-command-list-head">
        <div>
          <small>COMMAND CATALOG</small>
          <h2>系统命令库</h2>
          <p>{{ props.commands.length }} 条命令 · 默认供 Workflow 搜索</p>
        </div>
        <UiButton size="sm" variant="primary" @click="newCommand"><template #icon><Plus /></template>新建</UiButton>
      </div>
      <label class="admin-command-search"><Search :size="15" /><input v-model="search" type="search" placeholder="搜索 Key、名称或命令表达式" /></label>
      <div class="admin-command-filters" role="tablist" aria-label="命令状态筛选">
        <button v-for="option in [{ id: 'all', label: '全部' }, { id: 'enabled', label: '已启用' }, { id: 'disabled', label: '已停用' }]" :key="option.id" type="button" :class="statusFilter === option.id && 'active'" role="tab" :aria-selected="statusFilter === option.id" @click="statusFilter = option.id as typeof statusFilter">{{ option.label }}</button>
      </div>
      <div class="admin-command-list-scroll">
        <button v-for="command in filteredCommands" :key="command.id" type="button" :class="['admin-directory-item', command.id === props.selectedCommandId && 'active']" @click="selectCommand(command.id)">
          <span class="admin-command-item-title"><strong>{{ command.metadata?.name || command.name || command.key }}</strong><i :class="command.enabled !== false ? 'is-enabled' : 'is-disabled'">{{ command.enabled !== false ? "启用" : "停用" }}</i></span>
          <code>{{ command.expression }}</code>
          <small>{{ command.key }}<template v-if="command.metadata?.device"> · {{ command.metadata.device }}</template></small>
        </button>
        <div v-if="!filteredCommands.length" class="admin-command-empty"><Search :size="22" /><strong>{{ props.commands.length ? "没有匹配的命令" : "还没有系统命令" }}</strong><span>{{ props.commands.length ? "调整搜索词或状态筛选。" : "创建第一条系统命令开始测试。" }}</span></div>
      </div>
    </aside>

    <section class="admin-card admin-command-editor">
      <template v-if="isNew || selected">
        <header class="admin-command-editor-head">
          <div>
            <small>SYSTEM SOURCE</small>
            <h2>{{ isNew ? "新建系统命令" : "编辑系统命令" }}<span v-if="dirty" class="admin-unsaved-dot">未保存</span></h2>
            <p>{{ isNew ? "填写命令表达式和输出契约，保存后即可在 Workflow 中搜索。" : selected?.expression }}</p>
          </div>
          <UiIconButton v-if="selected" label="删除系统命令" variant="danger" @click="emit('delete', selected)"><Trash2 /></UiIconButton>
        </header>

        <div class="admin-command-editor-scroll">
          <section class="admin-command-section">
            <div class="admin-command-section-head"><div><h3>基本信息</h3><p>Key 用于稳定引用，名称用于列表展示。</p></div><label class="admin-command-switch"><input v-model="draft.enabled" type="checkbox" /><span>启用命令</span></label></div>
            <div class="admin-command-field-grid">
              <label class="field-label"><span>Key <b>*</b></span><input v-model="draft.key" placeholder="show_system_status" /></label>
              <label class="field-label"><span>名称 <b>*</b></span><input :value="metadataField('name')" placeholder="系统状态" @input="setMetadata('name', ($event.target as HTMLInputElement).value)" /></label>
              <label class="field-label span-2"><span>命令行表达式 <b>*</b></span><input v-model="draft.expression" class="admin-command-expression" placeholder="show interface <interface>" /><small class="field-help">支持关键字、&lt;参数&gt;、可选组和选项组；保存时由后端规范化和校验。</small></label>
              <label class="field-label span-2"><span>说明</span><textarea :value="metadataField('description')" rows="2" placeholder="这条命令采集什么信息？" @input="setMetadata('description', ($event.target as HTMLTextAreaElement).value)" /></label>
              <label class="field-label"><span>设备</span><input :value="metadataField('device')" placeholder="网络设备" @input="setMetadata('device', ($event.target as HTMLInputElement).value)" /></label>
              <label class="field-label"><span>行业</span><input :value="metadataField('industry')" placeholder="通用" @input="setMetadata('industry', ($event.target as HTMLInputElement).value)" /></label>
              <label class="field-label"><span>适用版本</span><input :value="metadataList('versions')" placeholder="留空表示全版本" @input="setMetadataList('versions', ($event.target as HTMLInputElement).value)" /></label>
              <label class="field-label"><span>标签</span><input :value="metadataList('tags')" placeholder="network, status" @input="setMetadataList('tags', ($event.target as HTMLInputElement).value)" /></label>
            </div>
          </section>

          <section class="admin-command-section">
            <div class="admin-command-section-head"><div><h3>回显示例</h3><p>保存完整触发命令和实际 stdout，便于后续解析和审阅。</p></div><span class="admin-command-counter">{{ sampleCount }} 个</span></div>
            <textarea v-model="jsonSamples" rows="9" spellcheck="false" class="workflow-code-input admin-command-json" placeholder="输入回显示例 JSON 数组" />
            <div class="admin-command-json-foot"><span>每项需要 `name`、`command` 和 `stdout`。</span><UiButton size="sm" variant="secondary" @click="formatJson('samples')"><template #icon><Braces /></template>格式化 JSON</UiButton></div>
          </section>

          <section class="admin-command-section">
            <div class="admin-command-section-head"><div><h3>输出 Schema</h3><p>根节点必须是 object，属性会投影为 Workflow 输出字段。</p></div><span class="admin-command-counter">{{ schemaPropertyCount }} 个字段</span></div>
            <textarea v-model="jsonSchema" rows="12" spellcheck="false" class="workflow-code-input admin-command-json" placeholder="输入根输出 JSON Schema" />
            <div class="admin-command-json-foot"><span>required 决定输出字段是否必填。</span><UiButton size="sm" variant="secondary" @click="formatJson('schema')"><template #icon><Braces /></template>格式化 JSON</UiButton></div>
          </section>

          <section class="admin-command-section">
            <div class="admin-command-section-head"><div><h3>TTP 原文</h3><p>仅保存原文，不参与当前版本的解析。</p></div></div>
            <textarea v-model="draft.ttp" rows="5" placeholder="可粘贴 TTP、厂商文档片段或审阅备注。" />
          </section>

          <div v-if="validationErrors.length || formError" class="admin-command-validation" role="alert"><AlertCircle :size="17" /><div><strong>保存前需要处理以下问题</strong><p v-if="formError">{{ formError }}</p><p v-for="error in validationErrors" :key="error">{{ error }}</p></div></div>
          <div v-else class="admin-command-valid"><CheckCircle2 :size="17" /><span>{{ dirty ? "内容已准备好，可以保存。" : "当前内容已保存。" }}</span></div>
        </div>

        <footer class="admin-command-editor-foot">
          <UiButton variant="secondary" :disabled="!dirty" @click="discardChanges"><template #icon><RotateCcw /></template>撤销修改</UiButton>
          <UiButton variant="primary" :disabled="!canSave" @click="save"><template #icon><Save /></template>{{ isNew ? "创建系统命令" : "保存修改" }}</UiButton>
        </footer>
      </template>
    </section>
  </section>
</template>
