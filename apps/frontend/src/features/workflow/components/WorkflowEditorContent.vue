<script setup lang="ts">
import { computed } from "vue";
import type { CollectionDefinition, SkillTagPayload, TagGroup, VersionedRef, WorkflowSelection } from "../../../types";
import type { WorkflowPathTargetChoice } from "../workflowPathEditing";
import type { useWorkflowEditor } from "../useWorkflowEditor";
import WorkflowCollectionLibrary from "./WorkflowCollectionLibrary.vue";
import WorkflowConclusionEditor from "./WorkflowConclusionEditor.vue";
import WorkflowMetadataEditor from "./WorkflowMetadataEditor.vue";
import WorkflowSettingsEditor from "./WorkflowSettingsEditor.vue";
import WorkflowStepEditor from "./WorkflowStepEditor.vue";
import { workflowConclusions, workflowSteps } from "../domain/utils";

const props = defineProps<{
  editor: ReturnType<typeof useWorkflowEditor>;
  readonly: boolean;
  tags: SkillTagPayload[];
  tagGroups: TagGroup[];
  tagBusy: boolean;
  tagError: string;
}>();
const emit = defineEmits<{
  select: [selection: WorkflowSelection];
  "select-catalog": [reference: VersionedRef];
  toast: [message: string];
  "tag-change": [tags: SkillTagPayload[]];
  "tag-save": [tags: SkillTagPayload[]];
  "request-delete": [type: "step" | "conclusion" | "call", id: string, stepId?: string];
}>();

const selectedStep = computed(() => {
  const selection = props.editor.selection.value;
  return selection.type === "step" && props.editor.bundle.value
    ? workflowSteps(props.editor.bundle.value).find((item) => item.id === selection.id)
    : undefined;
});
const selectedConclusion = computed(() => {
  const selection = props.editor.selection.value;
  return selection.type === "conclusion" && props.editor.bundle.value
    ? workflowConclusions(props.editor.bundle.value).find((item) => item.id === selection.id)
    : undefined;
});
const selectedCollectionRef = computed<VersionedRef | undefined>(() => {
  const selection = props.editor.selection.value;
  if (selection.type !== "collection") return undefined;
  const revisions = props.editor.catalog.value.filter((item) => item.id === selection.id).map((item) => item.revision);
  const revision = selection.revision ?? Math.max(...revisions);
  return Number.isFinite(revision) ? { id: selection.id, revision } : undefined;
});
const referencedDefinitionIds = computed(() => props.editor.bundle.value
  ? [...new Set(workflowSteps(props.editor.bundle.value).flatMap((step) => step.collectionCalls.map((call) => call.definition.id)))]
  : []);
const contentKey = computed(() => {
  const selection = props.editor.selection.value;
  if (selection.type === "inputs" || selection.type === "roles") return "global-inputs";
  return "id" in selection ? `${selection.type}:${selection.id}` : selection.type;
});

function select(selection: WorkflowSelection): void {
  emit("select", resolveSelection(selection));
}

function resolveSelection(selection: WorkflowSelection): WorkflowSelection {
  if (selection.type !== "collection" || !props.editor.bundle.value) return selection;
  const selectedId = props.editor.selection.value.type === "step" ? props.editor.selection.value.id : undefined;
  const steps = workflowSteps(props.editor.bundle.value);
  const step = steps.find((item) => item.id === selectedId && item.collectionCalls.some((call) => call.definition.id === selection.id))
    ?? steps.find((item) => item.collectionCalls.some((call) => call.definition.id === selection.id));
  const call = step?.collectionCalls.find((item) => item.definition.id === selection.id);
  return step && call ? { type: "step", id: step.id, section: "collections", itemId: call.id, field: selection.field } : selection;
}

function selectCatalog(reference: VersionedRef): void {
  emit("select-catalog", reference);
}

function addExistingCall(definition: CollectionDefinition): void {
  if (!selectedStep.value) return;
  const callId = props.editor.addCall(selectedStep.value.id, definition);
  emit("select", { type: "step", id: selectedStep.value.id, section: "collections", itemId: callId });
}

function addDraftCall(): void {
  if (!selectedStep.value) return;
  const result = props.editor.addDraftCollectionCall(selectedStep.value.id);
  if (result) emit("select", { type: "step", id: selectedStep.value.id, section: "collections", itemId: result.callId });
}

function updateDefinition(reference: VersionedRef, definition: CollectionDefinition): void {
  props.editor.editDefinition(reference, (draft) => Object.assign(draft, definition));
}

function updateCallDefinition(stepId: string, callId: string, definition: CollectionDefinition): void {
  const forked = props.editor.editCallDefinition(stepId, callId, (draft) => Object.assign(draft, definition));
  if (forked) emit("toast", "已创建采集定义副本，并将当前调用切换到副本。");
}

function addWorkflowPath(choice: WorkflowPathTargetChoice): void {
  if (selectedStep.value) props.editor.addPath(selectedStep.value.id, choice);
}

function retargetWorkflowPath(pathId: string, choice: WorkflowPathTargetChoice): void {
  if (selectedStep.value) props.editor.retargetPath(selectedStep.value.id, pathId, choice);
}

function openWorkflowTarget(targetId: string): void {
  const target = props.editor.bundle.value?.workflow.nodes.find((item) => item.id === targetId);
  if (target) select({ type: "stepType" in target ? "step" : "conclusion", id: target.id });
}
</script>

<template>
  <Transition name="workflow-editor-switch" mode="out-in">
    <div v-if="props.editor.bundle.value" :key="contentKey" class="workflow-editor-content">
      <WorkflowMetadataEditor v-if="props.editor.selection.value.type === 'metadata'" :metadata="props.editor.bundle.value.workflow.metadata" :readonly="props.readonly" :tags="props.tags" :tag-groups="props.tagGroups" :tag-busy="props.tagBusy" :tag-error="props.tagError" @change="props.editor.updateMetadata" @tag-change="emit('tag-change', $event)" @tag-save="emit('tag-save', $event)" />
      <WorkflowSettingsEditor v-else-if="props.editor.selection.value.type === 'inputs' || props.editor.selection.value.type === 'roles'" :inputs="props.editor.bundle.value.workflow.inputs" :roles="props.editor.bundle.value.workflow.deviceRoles" :target="props.editor.selection.value.type" :readonly="props.readonly" @add-input="props.editor.addInput" @update-input="props.editor.updateInput" @remove-input="props.editor.removeInput" @add-role="props.editor.addDeviceRole" @update-role="props.editor.updateDeviceRole" @remove-role="props.editor.removeDeviceRole" />
      <WorkflowCollectionLibrary v-else-if="props.editor.selection.value.type === 'collections' || props.editor.selection.value.type === 'collection'" :definitions="props.editor.catalog.value" :selected-ref="selectedCollectionRef" :changes="props.editor.changes.value" :referenced-definition-ids="referencedDefinitionIds" :readonly="props.readonly" @select="selectCatalog" @add="props.editor.addDefinition" @change="updateDefinition" @remove="props.editor.removeDraftDefinition" />
      <WorkflowStepEditor v-else-if="selectedStep" :step="selectedStep" :bundle="props.editor.bundle.value" :catalog="props.editor.catalog.value" :changes="props.editor.changes.value" :issues="props.editor.issues.value" :expression-diagnostics="props.editor.expressionDiagnostics.value" :target="props.editor.selection.value" :readonly="props.readonly" @change="props.editor.updateStep(selectedStep.id, $event)" @duplicate="props.editor.duplicateStep(selectedStep.id)" @remove="emit('request-delete', 'step', selectedStep.id)" @add-call="addExistingCall" @add-draft="addDraftCall" @call-change="(id, patch) => props.editor.updateCall(selectedStep!.id, id, patch)" @call-remove="emit('request-delete', 'call', $event, selectedStep.id)" @call-move="(id, direction) => props.editor.moveCall(selectedStep!.id, id, direction)" @call-reorder="props.editor.reorderCalls(selectedStep.id, $event)" @binding-change="(callId, inputId, binding) => props.editor.updateCallBinding(selectedStep!.id, callId, inputId, binding)" @definition-change="(callId, definition) => updateCallDefinition(selectedStep!.id, callId, definition)" @path-add="addWorkflowPath" @path-retarget="retargetWorkflowPath" @path-change="(id, patch) => props.editor.updatePath(selectedStep!.id, id, patch)" @path-remove="props.editor.removePath(selectedStep.id, $event)" @path-move="(id, direction) => props.editor.movePath(selectedStep!.id, id, direction)" @path-open-target="openWorkflowTarget" @predecessor-open="(id) => select({ type: 'step', id })" />
      <WorkflowConclusionEditor v-else-if="selectedConclusion" :conclusion="selectedConclusion" :bundle="props.editor.bundle.value" :readonly="props.readonly" @change="props.editor.updateConclusion(selectedConclusion.id, $event)" @remove="emit('request-delete', 'conclusion', selectedConclusion.id)" @predecessor-open="(id) => select({ type: 'step', id })" />
    </div>
  </Transition>
</template>
