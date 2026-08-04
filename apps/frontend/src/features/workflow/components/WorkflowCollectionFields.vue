<script setup lang="ts">
import { ChevronRight, Plus } from "lucide-vue-next";
import { ref } from "vue";
import TagInput from "../../../components/TagInput.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { CollectionDefinition, CollectionOutput, LogCollectionSpec, WorkflowParameter, WorkflowValidationIssue } from "../../../types";
import { cloneWorkflow, createWorkflowId } from "../domain/utils";
import { newWorkflowSchema } from "../workflowJsonSchema";
import WorkflowCollectionInputRows from "./WorkflowCollectionInputRows.vue";
import WorkflowCollectionOutputRows from "./WorkflowCollectionOutputRows.vue";
import WorkflowCliSpecFields from "./WorkflowCliSpecFields.vue";
import WorkflowConfirmModal from "./WorkflowConfirmModal.vue";
import WorkflowLogSpecFields from "./WorkflowLogSpecFields.vue";

const props = withDefaults(defineProps<{
  definition: CollectionDefinition;
  readonly: boolean;
  compact?: boolean;
  inlineDraft?: boolean;
  issues?: WorkflowValidationIssue[];
}>(), { compact: false, inlineDraft: false, issues: () => [] });
const emit = defineEmits<{ change: [definition: CollectionDefinition] }>();
const metadataOpen = ref(!props.inlineDraft);
const pendingCollectionType = ref<"cli" | "log" | null>(null);

function update(recipe: (draft: CollectionDefinition) => void): void {
  const draft = cloneWorkflow(props.definition);
  recipe(draft);
  emit("change", draft);
}

function list(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function addInput(): void {
  update((draft) => draft.inputs.push({ id: createWorkflowId("collection-input"), key: "", required: true, schema: newWorkflowSchema("string") }));
}

function updateInput(id: string, patch: Partial<WorkflowParameter>): void {
  update((draft) => Object.assign(draft.inputs.find((item) => item.id === id) ?? {}, patch));
}

function addOutput(): void {
  update((draft) => draft.outputs.push({ id: createWorkflowId("collection-output"), key: "", required: true, schema: newWorkflowSchema("string") }));
}

function updateOutput(id: string, patch: Partial<CollectionOutput>): void {
  update((draft) => Object.assign(draft.outputs.find((item) => item.id === id) ?? {}, patch));
}

function issue(field: string): WorkflowValidationIssue | undefined {
  return props.issues.find((item) => item.selection.type === "collection" && item.selection.id === props.definition.id && item.selection.field === field);
}

function removeOutput(id: string): void {
  update((draft) => {
    draft.outputs = draft.outputs.filter((item) => item.id !== id);
    if (draft.spec.collectionType === "log") {
      draft.spec.queries.forEach((query) => { query.outputIds = query.outputIds.filter((outputId) => outputId !== id); });
    }
  });
}

function changeCollectionType(type: "cli" | "log"): void {
  if (type === props.definition.spec.collectionType) return;
  pendingCollectionType.value = type;
}

function confirmCollectionType(): void {
  const type = pendingCollectionType.value;
  if (!type) return;
  update((draft) => {
    draft.spec = type === "cli"
      ? { collectionType: "cli", commandTemplate: "", outputSamples: [] }
      : { collectionType: "log", sqlDialect: "duckdb", queries: [], outputSamples: [] } satisfies LogCollectionSpec;
  });
  pendingCollectionType.value = null;
}
</script>

<template>
  <div :class="['workflow-collection-fields', props.compact && 'compact']">
    <section class="workflow-field-section workflow-collection-identity">
      <div class="workflow-form-grid">
        <label :class="['field-label', issue('metadata.name') && 'field-invalid']">
          <span>名称</span>
          <input :value="props.definition.metadata.name" :disabled="props.readonly" :aria-invalid="Boolean(issue('metadata.name'))" @input="update((draft) => { draft.metadata.name = ($event.target as HTMLInputElement).value; })" />
          <small v-if="issue('metadata.name')" class="field-error">{{ issue('metadata.name')?.message }}</small>
        </label>
        <label class="field-label"><span>Key</span><input :value="props.definition.key" :disabled="props.readonly" @input="update((draft) => { draft.key = ($event.target as HTMLInputElement).value; })" /></label>
      </div>
      <button class="workflow-section-toggle" type="button" :aria-expanded="metadataOpen" @click="metadataOpen = !metadataOpen">
        <ChevronRight :class="metadataOpen && 'open'" :size="15" />扩展元信息
        <small>{{ props.definition.metadata.industry || props.definition.metadata.device || props.definition.metadata.versions.length ? "已继承" : "可选" }}</small>
      </button>
      <Transition name="workflow-collapse">
        <div v-if="metadataOpen" class="workflow-form-grid workflow-metadata-fields">
          <label class="field-label span-2"><span>说明</span><textarea rows="3" :value="props.definition.metadata.description" :disabled="props.readonly" @input="update((draft) => { draft.metadata.description = ($event.target as HTMLTextAreaElement).value; })" /></label>
          <label class="field-label"><span>产业</span><input :value="props.definition.metadata.industry" :disabled="props.readonly" @input="update((draft) => { draft.metadata.industry = ($event.target as HTMLInputElement).value; })" /></label>
          <label class="field-label"><span>设备</span><input :value="props.definition.metadata.device" :disabled="props.readonly" @input="update((draft) => { draft.metadata.device = ($event.target as HTMLInputElement).value; })" /></label>
          <label class="field-label span-2"><span>适用版本</span><input :value="props.definition.metadata.versions.join(', ')" :disabled="props.readonly" @change="update((draft) => { draft.metadata.versions = list(($event.target as HTMLInputElement).value); })" /></label>
          <label class="field-label span-2"><span>Tags</span><TagInput :value="props.definition.metadata.tags" :disabled="props.readonly" placeholder="输入标签后按 Enter" @change="update((draft) => { draft.metadata.tags = $event; })" /></label>
        </div>
      </Transition>
    </section>

    <section class="workflow-field-section workflow-collection-type">
      <label class="field-label"><span>采集类型</span><select :value="props.definition.spec.collectionType" :disabled="props.readonly" @change="changeCollectionType(($event.target as HTMLSelectElement).value as 'cli' | 'log')"><option value="cli">CLI 命令</option><option value="log">日志聚合</option></select></label>
    </section>

    <WorkflowCliSpecFields v-if="props.definition.spec.collectionType === 'cli'" :definition="props.definition" :readonly="props.readonly" @change="update((draft) => { draft.spec = $event; })" />
    <WorkflowLogSpecFields v-else :definition="props.definition" :readonly="props.readonly" @change="update((draft) => { draft.spec = $event; })" />

    <section class="workflow-field-section">
      <div class="workflow-subhead"><div><h3>输入参数</h3><p>{{ props.definition.inputs.length }} 个参数</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addInput"><template #icon><Plus /></template>添加</UiButton></div>
      <WorkflowCollectionInputRows :items="props.definition.inputs" :readonly="props.readonly" :scalar-only="props.definition.spec.collectionType === 'log'" @change="updateInput" @remove="update((draft) => { draft.inputs = draft.inputs.filter((value) => value.id !== $event); })" />
      <p v-if="props.definition.inputs.length === 0" class="workflow-inline-empty">当前采集不需要输入参数</p>
    </section>

    <section class="workflow-field-section">
      <div class="workflow-subhead"><div><h3>输出字段</h3><p>{{ props.definition.outputs.length }} 个字段</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addOutput"><template #icon><Plus /></template>添加</UiButton></div>
      <WorkflowCollectionOutputRows :items="props.definition.outputs" :readonly="props.readonly" :scalar-only="props.definition.spec.collectionType === 'log'" @change="updateOutput" @remove="removeOutput" />
      <p v-if="props.definition.outputs.length === 0" class="workflow-inline-empty">尚未声明结构化输出</p>
    </section>

    <WorkflowConfirmModal
      v-if="pendingCollectionType"
      title="切换采集类型"
      description="切换类型会清空当前命令、SQL 和对应样例，但会保留元信息、输入和输出字段。"
      confirm-label="切换类型"
      tone="danger"
      @close="pendingCollectionType = null"
      @confirm="confirmCollectionType"
    />
  </div>
</template>
