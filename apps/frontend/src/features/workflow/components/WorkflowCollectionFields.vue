<script setup lang="ts">
import { ChevronRight, CirclePlus, Plus, Trash2 } from "lucide-vue-next";
import { ref } from "vue";
import TagInput from "../../../components/TagInput.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionDefinition, CollectionOutput, WorkflowParameter, WorkflowValidationIssue } from "../../../types";
import { cloneWorkflow, createWorkflowId } from "../domain/utils";
import WorkflowCollectionInputRows from "./WorkflowCollectionInputRows.vue";
import WorkflowCollectionOutputRows from "./WorkflowCollectionOutputRows.vue";

const props = withDefaults(defineProps<{
  definition: CollectionDefinition;
  readonly: boolean;
  compact?: boolean;
  inlineDraft?: boolean;
  issues?: WorkflowValidationIssue[];
}>(), { compact: false, inlineDraft: false, issues: () => [] });
const emit = defineEmits<{ change: [definition: CollectionDefinition] }>();
const metadataOpen = ref(!props.inlineDraft);

function update(recipe: (draft: CollectionDefinition) => void): void {
  const draft = cloneWorkflow(props.definition);
  recipe(draft);
  emit("change", draft);
}

function list(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function addInput(): void {
  update((draft) => draft.inputs.push({ id: createWorkflowId("collection-input"), key: "", name: "", description: "", dataType: "string", required: true }));
}

function updateInput(id: string, patch: Partial<WorkflowParameter>): void {
  update((draft) => Object.assign(draft.inputs.find((item) => item.id === id) ?? {}, patch));
}

function addOutput(): void {
  update((draft) => draft.outputs.push({ id: createWorkflowId("collection-output"), key: "", description: "", dataType: "string" }));
}

function updateOutput(id: string, patch: Partial<CollectionOutput>): void {
  update((draft) => Object.assign(draft.outputs.find((item) => item.id === id) ?? {}, patch));
}

function issue(field: string): WorkflowValidationIssue | undefined {
  return props.issues.find((item) => item.selection.type === "collection" && item.selection.id === props.definition.id && item.selection.field === field);
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

    <section :class="['workflow-field-section', issue('spec.commandTemplate') && 'field-invalid']">
      <div class="workflow-subhead"><div><h3>采集命令</h3><p>CLI 命令模板，可引用定义中的输入参数。</p></div></div>
      <input class="workflow-code-input workflow-command-input" type="text" spellcheck="false" :value="props.definition.spec.commandTemplate" :disabled="props.readonly" :aria-invalid="Boolean(issue('spec.commandTemplate'))" @input="update((draft) => { draft.spec.commandTemplate = ($event.target as HTMLInputElement).value; })" />
      <small v-if="issue('spec.commandTemplate')" class="field-error">{{ issue('spec.commandTemplate')?.message }}</small>
    </section>

    <section class="workflow-field-section">
      <div class="workflow-subhead"><div><h3>输入参数</h3><p>{{ props.definition.inputs.length }} 个参数</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addInput"><template #icon><Plus /></template>添加</UiButton></div>
      <WorkflowCollectionInputRows :items="props.definition.inputs" :readonly="props.readonly" @change="updateInput" @remove="update((draft) => { draft.inputs = draft.inputs.filter((value) => value.id !== $event); })" />
      <p v-if="props.definition.inputs.length === 0" class="workflow-inline-empty">当前采集不需要输入参数</p>
    </section>

    <section class="workflow-field-section">
      <div class="workflow-subhead"><div><h3>输出字段</h3><p>{{ props.definition.outputs.length }} 个字段</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addOutput"><template #icon><Plus /></template>添加</UiButton></div>
      <WorkflowCollectionOutputRows :items="props.definition.outputs" :readonly="props.readonly" @change="updateOutput" @remove="update((draft) => { draft.outputs = draft.outputs.filter((value) => value.id !== $event); })" />
      <p v-if="props.definition.outputs.length === 0" class="workflow-inline-empty">尚未声明结构化输出</p>
    </section>

    <section class="workflow-field-section">
      <div class="workflow-subhead"><div><h3>回显示例</h3><p>{{ props.definition.spec.outputSamples.length }} 个样例</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="update((draft) => draft.spec.outputSamples.push({ id: createWorkflowId('sample'), name: `示例 ${draft.spec.outputSamples.length + 1}`, stdout: '', inputValues: {} }))"><template #icon><CirclePlus /></template>添加</UiButton></div>
      <article v-for="sample in props.definition.spec.outputSamples" :key="sample.id" class="workflow-sample">
        <div><input :value="sample.name" aria-label="样例名称" :disabled="props.readonly" @input="update((draft) => { const target = draft.spec.outputSamples.find((item) => item.id === sample.id); if (target) target.name = ($event.target as HTMLInputElement).value; })" /><UiIconButton label="删除样例" size="sm" variant="danger" :disabled="props.readonly" @click="update((draft) => { draft.spec.outputSamples = draft.spec.outputSamples.filter((item) => item.id !== sample.id); })"><Trash2 /></UiIconButton></div>
        <textarea rows="5" spellcheck="false" :value="sample.stdout" :disabled="props.readonly" @input="update((draft) => { const target = draft.spec.outputSamples.find((item) => item.id === sample.id); if (target) target.stdout = ($event.target as HTMLTextAreaElement).value; })" />
      </article>
      <p v-if="props.definition.spec.outputSamples.length === 0" class="workflow-inline-empty">尚未添加回显示例</p>
    </section>
  </div>
</template>
