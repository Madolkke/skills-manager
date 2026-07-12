<script setup lang="ts">
import { AlertTriangle, LockKeyhole } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import InlineLoading from "../components/InlineLoading.vue";
import WorkflowCollectionLibrary from "../features/workflow/components/WorkflowCollectionLibrary.vue";
import WorkflowConfirmModal from "../features/workflow/components/WorkflowConfirmModal.vue";
import WorkflowConclusionEditor from "../features/workflow/components/WorkflowConclusionEditor.vue";
import WorkflowMetadataEditor from "../features/workflow/components/WorkflowMetadataEditor.vue";
import WorkflowPreviewPanel from "../features/workflow/components/WorkflowPreviewPanel.vue";
import WorkflowSettingsEditor from "../features/workflow/components/WorkflowSettingsEditor.vue";
import WorkflowSidebar from "../features/workflow/components/WorkflowSidebar.vue";
import WorkflowStepEditor from "../features/workflow/components/WorkflowStepEditor.vue";
import WorkflowSyncModal from "../features/workflow/components/WorkflowSyncModal.vue";
import WorkflowToolbar from "../features/workflow/components/WorkflowToolbar.vue";
import { workflowStatusLabel, workflowStatusTone } from "../features/workflow/domain/presentation";
import { workflowConclusions, workflowSteps } from "../features/workflow/domain/utils";
import { useWorkflowEditor } from "../features/workflow/useWorkflowEditor";
import { useWorkflowLayout } from "../features/workflow/useWorkflowLayout";
import type { WorkflowPathTargetChoice } from "../features/workflow/workflowPathEditing";
import { useWorkflowShortcuts } from "../features/workflow/useWorkflowShortcuts";
import { api, ApiError } from "../lib/api";
import type { CollectionDefinition, SkillDetail, ToastState, VersionedRef, WorkflowDetail, WorkflowSelection } from "../types";

type ConfirmAction = { type: "discard" } | { type: "step" | "conclusion" | "call"; id: string; stepId?: string };

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ back: []; refresh: []; dirty: [dirty: boolean]; toast: [toast: ToastState] }>();
const detail = ref<WorkflowDetail | null>(null);
const loading = ref(true);
const saving = ref(false);
const syncing = ref(false);
const loadError = ref("");
const actionError = ref("");
const syncError = ref("");
const syncOpen = ref(false);
const confirmAction = ref<ConfirmAction | null>(null);
const previewTab = ref<"graph" | "read" | "validation">("graph");
const editorPane = ref<HTMLElement | null>(null);
const editor = useWorkflowEditor(() => readOnly.value);
const layout = useWorkflowLayout();

const readOnly = computed(() => !detail.value?.capabilities.permissions["skill.edit"]);
const canCreateVersion = computed(() => Boolean(detail.value?.capabilities.permissions["skill.version.create"]));
const errors = computed(() => editor.issues.value.filter((item) => item.severity === "error"));
const canSync = computed(() => Boolean(detail.value && canCreateVersion.value && !editor.dirty.value && errors.value.length === 0 && !saving.value));
const selectedStep = computed(() => {
  const selection = editor.selection.value;
  return selection.type === "step" && editor.bundle.value
    ? workflowSteps(editor.bundle.value).find((item) => item.id === selection.id)
    : undefined;
});
const selectedConclusion = computed(() => {
  const selection = editor.selection.value;
  return selection.type === "conclusion" && editor.bundle.value
    ? workflowConclusions(editor.bundle.value).find((item) => item.id === selection.id)
    : undefined;
});
const selectedCollectionRef = computed<VersionedRef | undefined>(() => {
  const selection = editor.selection.value;
  if (selection.type !== "collection") return undefined;
  const revision = selection.revision ?? Math.max(...editor.catalog.value.filter((item) => item.id === selection.id).map((item) => item.revision));
  return Number.isFinite(revision) ? { id: selection.id, revision } : undefined;
});
const referencedDefinitionIds = computed(() => editor.bundle.value
  ? [...new Set(workflowSteps(editor.bundle.value).flatMap((step) => step.collectionCalls.map((call) => call.definition.id)))]
  : []);

onMounted(() => {
  window.addEventListener("beforeunload", beforeUnload);
  void load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", beforeUnload);
  emit("dirty", false);
});
watch(() => props.skill.skill.id, () => void load());
watch(editor.dirty, (dirty) => emit("dirty", dirty), { immediate: true });
useWorkflowShortcuts({
  canSave: () => editor.dirty.value && !readOnly.value && !saving.value,
  save: () => void save(),
  undo: editor.undo,
  redo: editor.redo,
  escape: closeTransientUi,
});

async function load(preserveContext = false): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    const [nextDetail, response] = await Promise.all([api.getWorkflow(props.skill.skill.id), api.listWorkflowCollections(props.skill.skill.id)]);
    detail.value = nextDetail;
    if (preserveContext && editor.bundle.value) editor.accepted(nextDetail, response.definitions);
    else editor.load(nextDetail, response.definitions);
  } catch (caught) {
    loadError.value = message(caught, "Workflow 加载失败。");
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  if (!editor.bundle.value || !editor.dirty.value || readOnly.value) return;
  const scrollTop = editorPane.value?.scrollTop ?? 0;
  saving.value = true;
  actionError.value = "";
  try {
    const nextDetail = await api.saveWorkflow(props.skill.skill.id, { document: editor.bundle.value, collection_changes: editor.changes.value });
    const response = await api.listWorkflowCollections(props.skill.skill.id);
    detail.value = nextDetail;
    editor.accepted(nextDetail, response.definitions);
    await nextTick();
    if (editorPane.value) editorPane.value.scrollTop = scrollTop;
    emit("refresh");
    emit("toast", { tone: "success", message: `Workflow revision ${nextDetail.revision} 已保存。` });
  } catch (caught) {
    actionError.value = message(caught, "Workflow 保存失败。");
  } finally {
    saving.value = false;
  }
}

async function sync(payload: { version: string; display_name?: string; change_summary: string }): Promise<void> {
  syncing.value = true;
  syncError.value = "";
  try {
    const result = await api.syncWorkflow(props.skill.skill.id, payload);
    syncOpen.value = false;
    await load(true);
    emit("refresh");
    const action = result.mode === "created" ? "已生成新版本" : result.mode === "reactivated" ? "已重新设为当前版本" : "当前版本已经是最新同步结果";
    emit("toast", { tone: "success", message: action });
  } catch (caught) {
    syncError.value = message(caught, "Workflow 同步失败。");
  } finally {
    syncing.value = false;
  }
}

function select(selection: WorkflowSelection): void {
  editor.selection.value = resolveSelection(selection);
}

function selectCatalog(reference: VersionedRef): void {
  editor.selection.value = { type: "collection", id: reference.id, revision: reference.revision };
}

function resolveSelection(selection: WorkflowSelection): WorkflowSelection {
  if (selection.type !== "collection" || !editor.bundle.value) return selection;
  const selectedId = editor.selection.value.type === "step" ? editor.selection.value.id : undefined;
  const steps = workflowSteps(editor.bundle.value);
  const step = steps.find((item) => item.id === selectedId && item.collectionCalls.some((call) => call.definition.id === selection.id))
    ?? steps.find((item) => item.collectionCalls.some((call) => call.definition.id === selection.id));
  const call = step?.collectionCalls.find((item) => item.definition.id === selection.id);
  return step && call ? { type: "step", id: step.id, section: "collections", itemId: call.id, field: selection.field } : selection;
}

function addExistingCall(definition: CollectionDefinition): void {
  if (!selectedStep.value) return;
  const callId = editor.addCall(selectedStep.value.id, definition);
  editor.selection.value = { type: "step", id: selectedStep.value.id, section: "collections", itemId: callId };
}

function addDraftCall(): void {
  if (!selectedStep.value) return;
  const result = editor.addDraftCollectionCall(selectedStep.value.id);
  if (result) editor.selection.value = { type: "step", id: selectedStep.value.id, section: "collections", itemId: result.callId };
}

function updateDefinition(reference: VersionedRef, definition: CollectionDefinition): void {
  editor.editDefinition(reference, (draft) => Object.assign(draft, definition));
}

function updateCallDefinition(stepId: string, callId: string, definition: CollectionDefinition): void {
  const forked = editor.editCallDefinition(stepId, callId, (draft) => Object.assign(draft, definition));
  if (forked) emit("toast", { tone: "info", message: "已创建采集定义副本，并将当前调用切换到副本。" });
}

function addWorkflowPath(choice: WorkflowPathTargetChoice): void {
  if (selectedStep.value) editor.addPath(selectedStep.value.id, choice);
}

function retargetWorkflowPath(pathId: string, choice: WorkflowPathTargetChoice): void {
  if (selectedStep.value) editor.retargetPath(selectedStep.value.id, pathId, choice);
}

function openWorkflowTarget(targetId: string): void {
  const target = editor.bundle.value?.workflow.nodes.find((item) => item.id === targetId);
  if (target) select({ type: "stepType" in target ? "step" : "conclusion", id: target.id });
}

function showValidation(): void {
  previewTab.value = "validation";
  layout.rightCollapsed.value = false;
}

function requestDelete(type: "step" | "conclusion" | "call", id: string, stepId?: string): void {
  confirmAction.value = { type, id, stepId };
}

function confirm(): void {
  const action = confirmAction.value;
  confirmAction.value = null;
  if (!action) return;
  if (action.type === "discard") editor.discard();
  else if (action.type === "step") editor.removeStep(action.id);
  else if (action.type === "conclusion") editor.removeConclusion(action.id);
  else if (action.type === "call" && action.stepId) {
    editor.removeCall(action.stepId, action.id);
    editor.selection.value = { type: "step", id: action.stepId, section: "collections" };
  }
}

function closeTransientUi(): void {
  if (confirmAction.value) confirmAction.value = null;
  else if (syncOpen.value) syncOpen.value = false;
  else if (editor.selection.value.type === "step" && editor.selection.value.itemId) editor.selection.value = { type: "step", id: editor.selection.value.id, section: editor.selection.value.section };
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!editor.dirty.value) return;
  event.preventDefault();
  event.returnValue = "";
}

function message(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}
</script>

<template>
  <section class="workflow-workbench-page">
    <WorkflowToolbar
      :title="detail?.document.workflow.metadata.name ?? skill.skill.slug"
      :revision="detail?.revision"
      :sync-label="detail ? workflowStatusLabel(detail.sync.status) : undefined"
      :dirty="editor.dirty.value"
      :readonly="readOnly"
      :saving="saving"
      :syncing="syncing"
      :issue-count="editor.issues.value.length"
      :can-undo="editor.canUndo.value"
      :can-redo="editor.canRedo.value"
      :can-sync="canSync"
      @back="emit('back')"
      @undo="editor.undo"
      @redo="editor.redo"
      @discard="confirmAction = { type: 'discard' }"
      @save="save"
      @sync="syncOpen = true"
      @validation="showValidation"
    />

    <div v-if="detail" class="workflow-workbench-status">
      <span :class="['workflow-status-sync', `tone-${workflowStatusTone(detail.sync.status)}`]">{{ workflowStatusLabel(detail.sync.status) }}</span>
      <span>最后保存 {{ new Date(detail.updated_at).toLocaleString() }}</span>
      <span v-if="readOnly"><LockKeyhole :size="13" />只读模式</span>
      <span v-if="editor.dirty.value">修改尚未写入服务端</span>
      <span v-else-if="errors.length" class="tone-danger"><AlertTriangle :size="13" />{{ errors.length }} 个错误阻止同步</span>
    </div>
    <div v-if="actionError" class="workflow-action-error"><AlertTriangle :size="15" />{{ actionError }}<button type="button" aria-label="关闭错误" @click="actionError = ''">×</button></div>

    <div v-if="loading" class="workflow-page-state"><InlineLoading label="正在加载 Workflow" /></div>
    <div v-else-if="loadError" class="workflow-page-state"><div class="form-error">{{ loadError }}</div><button class="secondary-button" type="button" @click="load()">重新加载</button></div>
    <div v-else-if="editor.bundle.value" class="workflow-workbench" :style="layout.gridStyle.value">
      <WorkflowSidebar
        :class="['workflow-pane-structure', layout.leftCollapsed.value && 'is-collapsed']"
        :bundle="editor.bundle.value"
        :selection="editor.selection.value"
        :issues="editor.issues.value"
        :readonly="readOnly"
        @select="select"
        @add-step="editor.addWorkflowStep"
        @add-conclusion="editor.addWorkflowConclusion"
        @move="editor.moveWorkflowNode"
        @reorder="editor.reorderWorkflowNodes"
      />
      <div :class="['workflow-panel-resizer', 'left', layout.leftCollapsed.value && 'is-collapsed']" role="separator" aria-label="调整结构面板宽度" @pointerdown="layout.startResize('left', $event)"><button class="workflow-panel-toggle" type="button" :title="layout.leftCollapsed.value ? '展开结构面板' : '折叠结构面板'" :aria-label="layout.leftCollapsed.value ? '展开结构面板' : '折叠结构面板'" @pointerdown.stop @click.stop="layout.leftCollapsed.value = !layout.leftCollapsed.value">{{ layout.leftCollapsed.value ? '›' : '‹' }}</button></div>

      <main ref="editorPane" class="workflow-editor-pane">
        <WorkflowMetadataEditor v-if="editor.selection.value.type === 'metadata'" :metadata="editor.bundle.value.workflow.metadata" :readonly="readOnly" @change="editor.updateMetadata" />
        <WorkflowSettingsEditor v-else-if="editor.selection.value.type === 'inputs'" mode="inputs" :inputs="editor.bundle.value.workflow.inputs" :roles="editor.bundle.value.workflow.deviceRoles" :readonly="readOnly" @add="editor.addInput" @update="editor.updateInput" @remove="editor.removeInput" />
        <WorkflowSettingsEditor v-else-if="editor.selection.value.type === 'roles'" mode="roles" :inputs="editor.bundle.value.workflow.inputs" :roles="editor.bundle.value.workflow.deviceRoles" :readonly="readOnly" @add="editor.addDeviceRole" @update="editor.updateDeviceRole" @remove="editor.removeDeviceRole" />
        <WorkflowCollectionLibrary v-else-if="editor.selection.value.type === 'collections' || editor.selection.value.type === 'collection'" :definitions="editor.catalog.value" :selected-ref="selectedCollectionRef" :changes="editor.changes.value" :referenced-definition-ids="referencedDefinitionIds" :readonly="readOnly" @select="selectCatalog" @add="editor.addDefinition" @change="updateDefinition" @remove="editor.removeDraftDefinition" />
        <WorkflowStepEditor
          v-else-if="selectedStep"
          :step="selectedStep"
          :bundle="editor.bundle.value"
          :catalog="editor.catalog.value"
          :changes="editor.changes.value"
          :issues="editor.issues.value"
          :target="editor.selection.value"
          :readonly="readOnly"
          @change="editor.updateStep(selectedStep.id, $event)"
          @duplicate="editor.duplicateStep(selectedStep.id)"
          @remove="requestDelete('step', selectedStep.id)"
          @add-input="editor.addStepInput(selectedStep.id)"
          @input-change="(id, patch) => editor.updateStepInput(selectedStep!.id, id, patch)"
          @input-remove="editor.removeStepInput(selectedStep.id, $event)"
          @add-call="addExistingCall"
          @add-draft="addDraftCall"
          @call-change="(id, patch) => editor.updateCall(selectedStep!.id, id, patch)"
          @call-remove="requestDelete('call', $event, selectedStep.id)"
          @call-move="(id, direction) => editor.moveCall(selectedStep!.id, id, direction)"
          @call-reorder="editor.reorderCalls(selectedStep.id, $event)"
          @binding-change="(callId, inputId, binding) => editor.updateCallBinding(selectedStep!.id, callId, inputId, binding)"
          @definition-change="(callId, definition) => updateCallDefinition(selectedStep!.id, callId, definition)"
          @path-add="addWorkflowPath"
          @path-retarget="retargetWorkflowPath"
          @path-change="(id, patch) => editor.updatePath(selectedStep!.id, id, patch)"
          @path-remove="editor.removePath(selectedStep.id, $event)"
          @path-move="(id, direction) => editor.movePath(selectedStep!.id, id, direction)"
          @path-open-target="openWorkflowTarget"
          @predecessor-open="(id) => select({ type: 'step', id })"
        />
        <WorkflowConclusionEditor v-else-if="selectedConclusion" :conclusion="selectedConclusion" :bundle="editor.bundle.value" :readonly="readOnly" @change="editor.updateConclusion(selectedConclusion.id, $event)" @remove="requestDelete('conclusion', selectedConclusion.id)" @predecessor-open="(id) => select({ type: 'step', id })" />
      </main>

      <div :class="['workflow-panel-resizer', 'right', layout.rightCollapsed.value && 'is-collapsed']" role="separator" aria-label="调整预览面板宽度" @pointerdown="layout.startResize('right', $event)"><button class="workflow-panel-toggle" type="button" :title="layout.rightCollapsed.value ? '展开预览面板' : '折叠预览面板'" :aria-label="layout.rightCollapsed.value ? '展开预览面板' : '折叠预览面板'" @pointerdown.stop @click.stop="layout.rightCollapsed.value = !layout.rightCollapsed.value">{{ layout.rightCollapsed.value ? '‹' : '›' }}</button></div>
      <WorkflowPreviewPanel v-model:tab="previewTab" :class="['workflow-pane-preview', layout.rightCollapsed.value && 'is-collapsed']" :bundle="editor.bundle.value" :catalog="editor.catalog.value" :issues="editor.issues.value" :selection="editor.selection.value" @select="select" />
    </div>

    <WorkflowSyncModal v-if="syncOpen && detail" :skill="skill" :revision="detail.revision" :issues="editor.issues.value" :busy="syncing" :error="syncError" @close="syncOpen = false; syncError = ''" @submit="sync" />
    <WorkflowConfirmModal v-if="confirmAction" :title="confirmAction.type === 'discard' ? '放弃未保存修改' : '确认删除'" :description="confirmAction.type === 'discard' ? '当前 Workflow 的所有未保存修改都将丢失。' : confirmAction.type === 'step' || confirmAction.type === 'conclusion' ? '节点及指向它的路径将被删除，此操作可在保存前撤销。' : '当前采集调用将被删除；若它是待入库定义的最后引用，定义也会一并清理。'" :confirm-label="confirmAction.type === 'discard' ? '放弃修改' : '删除'" tone="danger" @close="confirmAction = null" @confirm="confirm" />
  </section>
</template>
