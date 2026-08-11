<script setup lang="ts">
import { AlertTriangle, ChevronLeft, ChevronRight, X } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import InlineLoading from "../components/InlineLoading.vue";
import UiButton from "../components/ui/UiButton.vue";
import UiIconButton from "../components/ui/UiIconButton.vue";
import WorkflowConfirmModal from "../features/workflow/components/WorkflowConfirmModal.vue";
import WorkflowEditorContent from "../features/workflow/components/WorkflowEditorContent.vue";
import WorkflowImportModal from "../features/workflow/components/WorkflowImportModal.vue";
import WorkflowPreviewPanel from "../features/workflow/components/WorkflowPreviewPanel.vue";
import WorkflowSidebar from "../features/workflow/components/WorkflowSidebar.vue";
import WorkflowSyncModal from "../features/workflow/components/WorkflowSyncModal.vue";
import WorkflowToolbar from "../features/workflow/components/WorkflowToolbar.vue";
import { workflowStatusLabel } from "../features/workflow/domain/presentation";
import { workflowSteps } from "../features/workflow/domain/utils";
import { useWorkflowEditor } from "../features/workflow/useWorkflowEditor";
import { useWorkflowLayout } from "../features/workflow/useWorkflowLayout";
import { useWorkflowPersistence } from "../features/workflow/useWorkflowPersistence";
import { useWorkflowSkillTags } from "../features/workflow/useWorkflowSkillTags";
import { useWorkflowShortcuts } from "../features/workflow/useWorkflowShortcuts";
import { useWorkflowTransfer } from "../features/workflow/useWorkflowTransfer";
import type { CollectionDefinition, SkillDetail, ToastState, VersionedRef, WorkflowDetail, WorkflowSelection } from "../types";

type ConfirmAction = { type: "discard" } | { type: "step" | "conclusion" | "call"; id: string; stepId?: string };

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ back: []; refresh: []; dirty: [dirty: boolean]; toast: [toast: ToastState] }>();
const detail = ref<WorkflowDetail | null>(null);
const syncOpen = ref(false);
const confirmAction = ref<ConfirmAction | null>(null);
const confirmOpen = ref(false);
const previewTab = ref<"graph" | "read" | "validation" | "agent">("graph");
const editorPane = ref<HTMLElement | null>(null);
const importFileInput = ref<HTMLInputElement | null>(null);
const readOnly = computed(() => !detail.value?.capabilities.permissions["skill.edit"]);
const editor = useWorkflowEditor(() => readOnly.value);
const layout = useWorkflowLayout();
const { loading, saving, saveFeedback, syncing, loadError, actionError, syncError, syncConflictKey, load, save, sync } = useWorkflowPersistence({
  skillId: () => props.skill.skill.id,
  detail,
  editor,
  editorPane,
  readonly: () => readOnly.value,
  refresh: () => emit("refresh"),
  closeSync: () => { syncOpen.value = false; },
  toast: (toast) => emit("toast", toast),
});
const skillTags = useWorkflowSkillTags({
  skill: () => props.skill,
  refresh: () => emit("refresh"),
  toast: (toast) => emit("toast", toast),
});
const transfer = useWorkflowTransfer({
  skillId: () => props.skill.skill.id,
  skillSlug: () => props.skill.skill.slug,
  dirty: () => editor.dirty.value,
  readonly: () => readOnly.value,
  imported: acceptImportedWorkflow,
  toast: (toast) => emit("toast", toast),
});

const canCreateVersion = computed(() => Boolean(detail.value?.capabilities.permissions["skill.version.create"]));
const errors = computed(() => editor.issues.value.filter((item) => item.severity === "error"));
const canSync = computed(() => Boolean(detail.value && canCreateVersion.value && !editor.dirty.value && errors.value.length === 0 && !saving.value));

onMounted(() => {
  window.addEventListener("beforeunload", beforeUnload);
  void load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", beforeUnload);
  emit("dirty", false);
});
watch(() => props.skill.skill.id, () => {
  layout.setGraphExpanded(false);
  transfer.closeImport();
  void load();
});
watch(editor.dirty, (dirty) => emit("dirty", dirty), { immediate: true });
watch(editor.dirty, (dirty) => {
  if (dirty) saveFeedback.value = "idle";
});
watch(layout.graphExpanded, (expanded) => {
  if (expanded && editorPane.value?.contains(document.activeElement)) {
    (document.activeElement as HTMLElement).blur();
  }
});
useWorkflowShortcuts({
  canSave: () => editor.dirty.value && !readOnly.value && !saving.value,
  save: () => void save(),
  undo: editor.undo,
  redo: editor.redo,
  escape: closeTransientUi,
});

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

function showValidation(): void {
  layout.setGraphExpanded(false);
  previewTab.value = "validation";
  layout.rightCollapsed.value = false;
}

function acceptImportedWorkflow(nextDetail: WorkflowDetail, definitions: CollectionDefinition[]): void {
  detail.value = nextDetail;
  editor.load(nextDetail, definitions);
  editor.selection.value = { type: "metadata" };
  emit("refresh");
}

function openImportPicker(): void {
  importFileInput.value?.click();
}

async function selectImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  await transfer.selectFile(input.files);
  input.value = "";
}

function requestDelete(type: "step" | "conclusion" | "call", id: string, stepId?: string): void {
  confirmAction.value = { type, id, stepId };
  confirmOpen.value = true;
}

function requestDiscard(): void {
  confirmAction.value = { type: "discard" };
  confirmOpen.value = true;
}

function confirm(): void {
  const action = confirmAction.value;
  confirmOpen.value = false;
  if (!action) return;
  if (action.type === "discard") {
    editor.discard();
    editor.selection.value = { type: "metadata" };
  }
  else if (action.type === "step") editor.removeStep(action.id);
  else if (action.type === "conclusion") editor.removeConclusion(action.id);
  else if (action.type === "call" && action.stepId) {
    editor.removeCall(action.stepId, action.id);
    editor.selection.value = { type: "step", id: action.stepId, section: "collections" };
  }
}

function finishConfirmClose(): void {
  if (!confirmOpen.value) confirmAction.value = null;
}

function closeTransientUi(): void {
  if (transfer.candidate.value) transfer.closeImport();
  else if (confirmOpen.value) confirmOpen.value = false;
  else if (syncOpen.value) syncOpen.value = false;
  else if (layout.graphExpanded.value) layout.setGraphExpanded(false);
  else if (editor.selection.value.type === "step" && editor.selection.value.itemId) editor.selection.value = { type: "step", id: editor.selection.value.id, section: editor.selection.value.section };
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!editor.dirty.value) return;
  event.preventDefault();
  event.returnValue = "";
}

</script>

<template>
  <section class="workflow-workbench-page">
    <WorkflowToolbar
      :title="detail?.document.workflow.metadata.name ?? skill.skill.slug"
      :revision="detail?.revision"
      :sync-label="detail ? workflowStatusLabel(detail.sync.status) : undefined"
      :last-saved-at="detail?.updated_at"
      :dirty="editor.dirty.value"
      :readonly="readOnly"
      :save-state="saving ? 'loading' : saveFeedback"
      :syncing="syncing"
      :issue-count="editor.issues.value.length"
      :can-undo="editor.canUndo.value"
      :can-redo="editor.canRedo.value"
      :can-sync="canSync"
      :transferring="transfer.importing.value || transfer.exporting.value"
      @back="emit('back')"
      @undo="editor.undo"
      @redo="editor.redo"
      @discard="requestDiscard"
      @save="save"
      @sync="syncOpen = true"
      @validation="showValidation"
      @export="transfer.exportWorkflow"
      @import="openImportPicker"
    />
    <input ref="importFileInput" hidden type="file" accept=".json,application/json" @change="selectImportFile">

    <Transition name="workflow-error-strip">
      <div v-if="actionError" class="workflow-action-error"><AlertTriangle :size="15" />{{ actionError }}<UiIconButton label="关闭错误" size="sm" variant="ghost" @click="actionError = ''"><X /></UiIconButton></div>
    </Transition>

    <div v-if="loading" class="workflow-page-state"><InlineLoading label="正在加载 Workflow" /></div>
    <div v-else-if="loadError" class="workflow-page-state"><div class="form-error">{{ loadError }}</div><UiButton variant="secondary" @click="load()">重新加载</UiButton></div>
    <div v-else-if="editor.bundle.value" :class="['workflow-workbench', layout.resizing.value && 'is-resizing', layout.graphExpanded.value && 'is-graph-expanded']" :style="layout.gridStyle.value">
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
      <div :class="['workflow-panel-resizer', 'left', layout.leftCollapsed.value && 'is-collapsed']" role="separator" aria-label="调整结构面板宽度" @pointerdown="layout.startResize('left', $event)"><button class="workflow-panel-toggle" type="button" :title="layout.leftCollapsed.value ? '展开结构面板' : '折叠结构面板'" :aria-label="layout.leftCollapsed.value ? '展开结构面板' : '折叠结构面板'" @pointerdown.stop @click.stop="layout.toggle('left')"><ChevronRight v-if="layout.leftCollapsed.value" :size="16" /><ChevronLeft v-else :size="16" /></button></div>

      <main ref="editorPane" class="workflow-editor-pane" :aria-hidden="layout.graphExpanded.value" :inert="layout.graphExpanded.value">
        <WorkflowEditorContent
          v-if="detail"
          :editor="editor"
          :readonly="readOnly"
          :skill-id="skill.skill.id"
          :saved-bundle="detail.document"
          :saved-revision="detail.revision"
          :workflow-dirty="editor.dirty.value"
          :tags="skillTags.tags.value"
          :tag-groups="skillTags.groups.value"
          :tag-busy="skillTags.busy.value"
          :tag-error="skillTags.error.value"
          @select="select"
          @select-catalog="selectCatalog"
          @tag-change="skillTags.update"
          @tag-save="skillTags.save"
          @toast="emit('toast', { tone: 'info', message: $event })"
          @request-delete="requestDelete"
        />
      </main>

      <div :class="['workflow-panel-resizer', 'right', layout.rightCollapsed.value && 'is-collapsed', layout.graphExpanded.value && 'is-obscured']" role="separator" aria-label="调整预览面板宽度" :aria-hidden="layout.graphExpanded.value" @pointerdown="layout.startResize('right', $event)"><button class="workflow-panel-toggle" type="button" :title="layout.rightCollapsed.value ? '展开预览面板' : '折叠预览面板'" :aria-label="layout.rightCollapsed.value ? '展开预览面板' : '折叠预览面板'" @pointerdown.stop @click.stop="layout.toggle('right')"><ChevronLeft v-if="layout.rightCollapsed.value" :size="16" /><ChevronRight v-else :size="16" /></button></div>
      <WorkflowPreviewPanel v-model:tab="previewTab" v-model:expanded="layout.graphExpanded.value" :class="['workflow-pane-preview', layout.rightCollapsed.value && !layout.graphExpanded.value && 'is-collapsed', layout.graphExpanded.value && 'is-expanded']" :skill-id="skill.skill.id" :revision="detail?.revision" :dirty="editor.dirty.value" :readonly="readOnly" :bundle="editor.bundle.value" :catalog="editor.catalog.value" :issues="editor.issues.value" :selection="editor.selection.value" @select="select" />
    </div>

    <WorkflowSyncModal
      v-if="detail"
      :open="syncOpen"
      :skill="skill"
      :revision="detail.revision"
      :recovery-key="syncConflictKey"
      :busy="syncing"
      :error="syncError"
      @close="syncOpen = false; syncError = ''"
      @previewed="syncError = ''"
      @submit="sync"
    />
    <WorkflowImportModal
      v-if="transfer.candidate.value"
      :candidate="transfer.candidate.value"
      :current-workflow-name="detail?.document.workflow.metadata.name ?? skill.skill.slug"
      :busy="transfer.importing.value"
      :error="transfer.importError.value"
      @close="transfer.closeImport"
      @confirm="transfer.confirmImport"
    />
    <WorkflowConfirmModal v-if="confirmAction" :open="confirmOpen" :title="confirmAction.type === 'discard' ? '放弃未保存修改' : '确认删除'" :description="confirmAction.type === 'discard' ? '当前 Workflow 的所有未保存修改都将丢失。' : confirmAction.type === 'step' || confirmAction.type === 'conclusion' ? '节点及指向它的路径将被删除，此操作可在保存前撤销。' : '当前采集调用将被删除；若它是待入库定义的最后引用，定义也会一并清理。'" :confirm-label="confirmAction.type === 'discard' ? '放弃修改' : '删除'" tone="danger" @close="confirmOpen = false" @closed="finishConfirmClose" @confirm="confirm" />
  </section>
</template>
