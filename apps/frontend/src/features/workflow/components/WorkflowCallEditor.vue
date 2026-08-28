<script setup lang="ts">
import { AlertTriangle, ChevronDown, ChevronUp, GitFork, GripVertical, Pencil, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionCall, CollectionDefinition, DeviceRole, WorkflowBinding, WorkflowBundle, WorkflowCollectionChange, WorkflowParameter, WorkflowValidationIssue } from "../../../types";
import { collectionContentSummary, collectionTypeLabel, isConfigCollection, isLogCollection } from "../domain/collectionPresentation";
import { findCollection } from "../domain/utils";
import type { WorkflowBindingCall } from "../workflowExpressionScope";
import { parseScalarLiteral, workflowSchemaTitle, workflowValueMatchesSchema } from "../workflowJsonSchema";
import { resolveWorkflowDeviceField, workflowDeviceFieldCandidates } from "../workflowDeviceRoleBindings";
import { workflowBindingExpressionVariables } from "../workflowExpressionVariables";
import WorkflowExpressionEditor from "./WorkflowExpressionEditor.vue";
import WorkflowCollectionFields from "./WorkflowCollectionFields.vue";
import WorkflowJsonValueModal from "./WorkflowJsonValueModal.vue";

const props = defineProps<{
  call: CollectionCall;
  stepId: string;
  bundle: WorkflowBundle;
  definition?: CollectionDefinition;
  workflowInputs: WorkflowParameter[];
  availableBindingCalls: WorkflowBindingCall[];
  catalog: CollectionDefinition[];
  roles: DeviceRole[];
  readonly: boolean;
  expanded: boolean;
  index: number;
  total: number;
  pendingOperation?: WorkflowCollectionChange["operation"];
  issues: WorkflowValidationIssue[];
}>();
const emit = defineEmits<{
  toggle: [];
  change: [patch: Partial<CollectionCall>];
  binding: [inputId: string, binding: WorkflowBinding | null];
  definition: [definition: CollectionDefinition];
  remove: [];
  move: [direction: -1 | 1];
}>();

const requiredInputs = computed(() => props.definition?.inputs.filter((item) => item.required) ?? []);
const boundCount = computed(() => requiredInputs.value.filter((item) => {
  const binding = props.call.inputBindings[item.id];
  return Boolean(binding && (binding.kind === "expression"
    ? binding.expression.trim() !== ""
    : binding.kind !== "literal" || (binding.value !== null && binding.value !== undefined && binding.value !== "")));
}).length);
const issueCount = computed(() => props.issues.length);
const displayName = computed(() => props.call.name || props.definition?.metadata.name || "未命名采集");
const structuredLiteralId = ref<string | null>(null);
const structuredLiteral = computed(() => props.definition?.inputs.find((item) => item.id === structuredLiteralId.value));
const previousOutputs = computed(() => props.availableBindingCalls.flatMap(({ call, step }) => {
  const definition = findCollection(props.catalog, call.definition);
  return definition?.outputs.map((output) => ({ call, output, definition, step })) ?? [];
}));
const deviceFields = computed(() => workflowDeviceFieldCandidates(props.roles, props.call.deviceRoleId));
const expressionVariables = computed(() => workflowBindingExpressionVariables(props.bundle, props.stepId, props.call.id));
function selectedDeviceField(inputId: string) {
  const binding = props.call.inputBindings[inputId];
  if (binding?.kind !== "device_role_field") return null;
  return resolveWorkflowDeviceField(props.roles, binding.reference.role_id, binding.reference.path).candidate;
}

watch(() => props.definition?.spec.collectionType, (type, previous) => {
  if ((type === "log" || type === "config") && previous && previous !== type && !props.readonly) {
    emit("change", { ...(type === "log" ? { deviceRoleId: undefined } : {}), sampleCount: 1 });
  }
});

function bindingKind(inputId: string): string {
  return props.call.inputBindings[inputId]?.kind ?? "";
}

function deviceBindingValue(inputId: string): string {
  const binding = props.call.inputBindings[inputId];
  return binding?.kind === "device_role_field" ? JSON.stringify(binding.reference) : "";
}

function deviceBindingOptionValue(item: { roleId: string; path: string }): string {
  return JSON.stringify({ role_id: item.roleId, path: item.path });
}

function selectDeviceBinding(inputId: string, value: string): void {
  try {
    const reference = JSON.parse(value) as { role_id?: string; path?: string };
    emit("binding", inputId, { kind: "device_role_field", reference: { role_id: reference.role_id ?? "", path: reference.path ?? "" } });
  } catch {
    emit("binding", inputId, { kind: "device_role_field", reference: { role_id: "", path: "" } });
  }
}

function workflowInputBindingValue(inputId: string): string {
  const binding = props.call.inputBindings[inputId];
  return binding?.kind === "workflow_input" ? binding.reference.input_id : "";
}

function collectionBindingValue(inputId: string): string {
  const binding = props.call.inputBindings[inputId];
  return binding?.kind === "collection_output" ? `${binding.reference.call_id}:${binding.reference.output_id}` : ":";
}

function expressionBindingValue(inputId: string): string {
  const binding = props.call.inputBindings[inputId];
  return binding?.kind === "expression" ? binding.expression : "";
}

function setBinding(inputId: string, kind: string): void {
  if (!kind) return emit("binding", inputId, null);
  if (kind !== "literal" && kind !== "workflow_input" && kind !== "collection_output" && kind !== "device_role_field" && kind !== "expression") return;
  if (kind === "expression") return emit("binding", inputId, { kind, reference: {}, expression: "" });
  if (kind === "literal") return emit("binding", inputId, { kind, reference: {}, value: "" });
  if (kind === "collection_output") {
    const item = previousOutputs.value[0];
    return emit("binding", inputId, { kind, reference: item ? { call_id: item.call.id, output_id: item.output.id } : { call_id: "", output_id: "" } });
  }
  if (kind === "device_role_field") {
    const item = deviceFields.value[0];
    return emit("binding", inputId, item ? { kind, reference: { role_id: item.roleId, path: item.path } } : { kind, reference: { role_id: "", path: "" } });
  }
  const input = props.workflowInputs[0];
  emit("binding", inputId, { kind: "workflow_input", reference: input ? { input_id: input.id } : { input_id: "" } });
}

function setScalarLiteral(input: WorkflowParameter, value: string): void {
  emit("binding", input.id, { kind: "literal", reference: {}, value: parseScalarLiteral(value, input.schema) });
}

function literalMismatch(input: WorkflowParameter): boolean {
  const binding = props.call.inputBindings[input.id];
  return binding?.kind === "literal" && !workflowValueMatchesSchema(binding.value, input.schema);
}

function hasIssue(field: string): boolean {
  return props.issues.some((item) => item.selection.type === "step" && item.selection.itemId === props.call.id && item.selection.field === field);
}

function expressionDiagnostics(inputId: string) {
  return props.issues
    .filter((item) => item.selection.type === "step" && item.selection.itemId === props.call.id && item.selection.field === `binding.${inputId}`)
    .map((item) => ({ severity: "error" as const, code: item.code, message: item.message, start: 0, end: Math.max(expressionBindingValue(inputId).length, 1) }));
}

function operationLabel(): string {
  if (props.pendingOperation === "create") return "待入库";
  if (props.pendingOperation === "fork") return "独立副本";
  if (props.pendingOperation === "revise") return "待修订";
  return `r${props.definition?.revision ?? props.call.definition.revision}`;
}
</script>

<template>
  <article :class="['workflow-call-card', props.expanded && 'expanded', issueCount && 'has-issues']" :data-sort-id="props.call.id" :data-workflow-item="props.call.id" :data-workflow-index="props.index">
    <header class="workflow-call-summary">
      <button class="workflow-drag-handle" type="button" title="拖动排序" aria-label="拖动采集排序" :disabled="props.readonly"><GripVertical :size="15" /></button>
      <button class="workflow-call-summary-main" type="button" @click="emit('toggle')">
        <span class="workflow-call-title"><strong :title="displayName">{{ displayName }}</strong><code v-if="props.call.key" :title="props.call.key">{{ props.call.key }}</code></span>
        <span class="workflow-call-command" :title="collectionContentSummary(props.definition)">{{ collectionContentSummary(props.definition) }}</span>
        <span class="workflow-call-facts">
          <i>{{ collectionTypeLabel(props.definition) }}</i>
          <i v-if="isLogCollection(props.definition)">全局日志</i>
          <template v-else><i>{{ props.roles.find((item) => item.id === props.call.deviceRoleId)?.name || "单设备" }}</i><i>采集 {{ props.call.sampleCount }} 次</i></template>
          <i v-if="requiredInputs.length">绑定 {{ boundCount }}/{{ requiredInputs.length }}</i>
        </span>
      </button>
      <span :class="['workflow-call-revision', props.pendingOperation && 'pending']">{{ operationLabel() }}</span>
      <span v-if="issueCount" class="workflow-call-issue"><AlertTriangle :size="12" />{{ issueCount }}</span>
      <div class="workflow-row-actions">
        <UiIconButton label="上移采集" size="sm" :disabled="props.readonly || props.index === 0" @click="emit('move', -1)"><ChevronUp /></UiIconButton>
        <UiIconButton label="下移采集" size="sm" :disabled="props.readonly || props.index === props.total - 1" @click="emit('move', 1)"><ChevronDown /></UiIconButton>
        <UiIconButton label="删除采集" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove')"><Trash2 /></UiIconButton>
      </div>
      <ChevronDown :class="['workflow-call-toggle', props.expanded && 'expanded']" :size="16" />
    </header>

    <Transition name="workflow-expand">
      <div v-if="props.expanded" class="workflow-call-body">
        <section class="workflow-call-settings">
          <div class="workflow-form-grid compact-grid">
            <label class="field-label"><span>调用名称</span><input :value="props.call.name" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label>
            <label class="field-label"><span>调用 Key</span><input :value="props.call.key" :disabled="props.readonly" @input="emit('change', { key: ($event.target as HTMLInputElement).value })" /></label>
            <label v-if="!isLogCollection(props.definition)" :class="['field-label', hasIssue('deviceRoleId') && 'field-invalid']"><span>设备角色</span><select :value="props.call.deviceRoleId ?? ''" :disabled="props.readonly" @change="emit('change', { deviceRoleId: ($event.target as HTMLSelectElement).value || undefined })"><option value="">单设备</option><option v-for="role in props.roles" :key="role.id" :value="role.id">{{ role.name }}</option></select></label>
            <label v-if="!isLogCollection(props.definition) && !isConfigCollection(props.definition)" :class="['field-label', hasIssue('sampleCount') && 'field-invalid']"><span>采集次数</span><input type="number" min="1" :value="props.call.sampleCount" :disabled="props.readonly" @input="emit('change', { sampleCount: Number(($event.target as HTMLInputElement).value) })" /></label>
          </div>
        </section>

        <section v-if="props.definition?.inputs.length" class="workflow-call-bindings">
          <div class="workflow-subhead"><div><h4>参数绑定</h4><p>{{ boundCount }}/{{ requiredInputs.length }} 个必填参数已绑定</p></div></div>
          <div v-for="input in props.definition.inputs" :key="input.id" :class="['workflow-binding-row', hasIssue(`binding.${input.id}`) && 'field-invalid']">
            <span><strong>{{ workflowSchemaTitle(input.schema, input.key) }}</strong><small>{{ input.key }} · {{ input.schema.type ?? "any" }}</small></span>
            <select :value="bindingKind(input.id)" :disabled="props.readonly" @change="setBinding(input.id, ($event.target as HTMLSelectElement).value)"><option value="">未绑定</option><option value="workflow_input">全局输入</option><option value="device_role_field">设备角色参数</option><option value="collection_output">前序采集输出</option><option value="expression">表达式</option><option value="literal">固定值</option></select>
            <select v-if="bindingKind(input.id) === 'workflow_input'" :value="workflowInputBindingValue(input.id)" :disabled="props.readonly" @change="emit('binding', input.id, { kind: 'workflow_input', reference: { input_id: ($event.target as HTMLSelectElement).value } })"><option v-for="item in props.workflowInputs" :key="item.id" :value="item.id">{{ workflowSchemaTitle(item.schema, item.key) }}</option></select>
            <select v-else-if="bindingKind(input.id) === 'collection_output'" :value="collectionBindingValue(input.id)" :disabled="props.readonly" @change="{ const [callId, outputId] = ($event.target as HTMLSelectElement).value.split(':'); emit('binding', input.id, { kind: 'collection_output', reference: { call_id: callId ?? '', output_id: outputId ?? '' } }); }"><option v-if="previousOutputs.length === 0" value=":">没有可用的前序输出</option><option v-for="item in previousOutputs" :key="`${item.call.id}:${item.output.id}`" :value="`${item.call.id}:${item.output.id}`">{{ item.step.name }} · {{ item.call.name || item.definition.metadata.name }} · {{ workflowSchemaTitle(item.output.schema, item.output.key) }}</option></select>
            <select v-else-if="bindingKind(input.id) === 'device_role_field'" :value="deviceBindingValue(input.id)" :disabled="props.readonly" @change="selectDeviceBinding(input.id, ($event.target as HTMLSelectElement).value)"><option v-if="deviceFields.length === 0" value="">没有可用的设备角色字段</option><option v-if="props.call.inputBindings[input.id]?.kind === 'device_role_field' && !selectedDeviceField(input.id)" :value="deviceBindingValue(input.id)">引用已失效</option><option v-for="item in deviceFields" :key="`${item.roleId}:${item.path}`" :value="deviceBindingOptionValue(item)">{{ item.roleName }} ({{ item.roleKey }}) · {{ item.path }} · {{ item.schema.type ?? 'any' }}</option></select>
            <WorkflowExpressionEditor v-else-if="bindingKind(input.id) === 'expression'" :value="expressionBindingValue(input.id)" :variables="expressionVariables" :diagnostics="expressionDiagnostics(input.id)" :readonly="props.readonly" placeholder="输入参数表达式" :aria-label="`${workflowSchemaTitle(input.schema, input.key)}表达式`" @change="emit('binding', input.id, { kind: 'expression', reference: {}, expression: $event })" />
            <select v-else-if="bindingKind(input.id) === 'literal' && input.schema.type === 'boolean'" :value="String(props.call.inputBindings[input.id]?.value ?? false)" :disabled="props.readonly" @change="setScalarLiteral(input, ($event.target as HTMLSelectElement).value)"><option value="true">true</option><option value="false">false</option></select>
            <button v-else-if="bindingKind(input.id) === 'literal' && (input.schema.type === 'object' || input.schema.type === 'array' || !input.schema.type)" type="button" :class="['workflow-literal-json-button', literalMismatch(input) && 'has-warning']" :disabled="props.readonly" @click="structuredLiteralId = input.id"><Pencil :size="14" />编辑 JSON<span v-if="literalMismatch(input)">Schema 不匹配</span></button>
            <input v-else-if="bindingKind(input.id) === 'literal'" :type="input.schema.type === 'integer' || input.schema.type === 'number' ? 'number' : 'text'" :step="input.schema.type === 'integer' ? '1' : 'any'" :class="literalMismatch(input) && 'field-warning'" :value="String(props.call.inputBindings[input.id]?.value ?? '')" :disabled="props.readonly" @input="setScalarLiteral(input, ($event.target as HTMLInputElement).value)" />
          </div>
        </section>

        <section v-if="props.definition && props.pendingOperation === 'create'" class="workflow-inline-definition workflow-inline-draft">
          <header><div><strong>新采集定义</strong><span>保存 Workflow 后进入全局采集库</span></div></header>
          <WorkflowCollectionFields inline-draft :definition="props.definition" :readonly="props.readonly || Boolean(props.definition.sourceSystemCommandId)" :issues="props.issues" @change="emit('definition', $event)" />
        </section>
        <details v-else-if="props.definition" class="workflow-inline-definition">
          <summary><GitFork :size="14" />编辑采集定义 <span>{{ props.pendingOperation === "fork" ? "当前调用使用副本" : "首次修改将自动创建副本" }}</span></summary>
          <WorkflowCollectionFields compact :definition="props.definition" :readonly="props.readonly || Boolean(props.definition.sourceSystemCommandId)" :issues="props.issues" @change="emit('definition', $event)" />
        </details>
      </div>
    </Transition>
    <WorkflowJsonValueModal v-if="structuredLiteral" :open="Boolean(structuredLiteral)" :value="props.call.inputBindings[structuredLiteral.id]?.value" :schema="structuredLiteral.schema" :field-name="workflowSchemaTitle(structuredLiteral.schema, structuredLiteral.key)" :readonly="props.readonly" @close="structuredLiteralId = null" @confirm="emit('binding', structuredLiteral.id, { kind: 'literal', reference: {}, value: $event }); structuredLiteralId = null" />
  </article>
</template>
