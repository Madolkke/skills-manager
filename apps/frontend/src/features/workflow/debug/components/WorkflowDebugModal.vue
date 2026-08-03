<script setup lang="ts">
import { Plus, Trash2 } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";
import Modal from "../../../../components/Modal.vue";
import UiButton from "../../../../components/ui/UiButton.vue";
import UiIconButton from "../../../../components/ui/UiIconButton.vue";
import WorkflowConfirmModal from "../../components/WorkflowConfirmModal.vue";
import type { WorkflowBundle, WorkflowDebugCase, WorkflowStep } from "../../../../types";
import type { WorkflowDebugApi } from "../api";
import {
  newWorkflowDebugCaseDraft, workflowDebugCaseDraft, workflowDebugCasePayload,
  workflowDebugDraftDirty, workflowDebugDraftValid, type WorkflowDebugCaseDraft,
} from "../form";
import { useWorkflowStepDebug } from "../useWorkflowStepDebug";
import WorkflowDebugCaseEditor from "./WorkflowDebugCaseEditor.vue";
import WorkflowDebugRunPanel from "./WorkflowDebugRunPanel.vue";

const props = defineProps<{
  open: boolean;
  skillId: string;
  bundle: WorkflowBundle;
  revision: number;
  step: WorkflowStep;
  workflowDirty: boolean;
  client?: WorkflowDebugApi;
}>();
const emit = defineEmits<{ close: [] }>();
const selectedCaseId = ref<string | null>(null);
const draft = ref<WorkflowDebugCaseDraft>(newWorkflowDebugCaseDraft(props.step, 0));
const deleteOpen = ref(false);
const debug = useWorkflowStepDebug({ skillId: () => props.skillId, stepId: () => props.step.id, client: props.client });

const selectedCase = computed(() => debug.cases.value.find((item) => item.id === selectedCaseId.value) ?? null);
const draftValid = computed(() => workflowDebugDraftValid(draft.value, props.step, props.bundle));
const caseDirty = computed(() => workflowDebugDraftDirty(draft.value, selectedCase.value));
const startDisabledReason = computed(() => {
  if (props.workflowDirty) return "请先保存 Workflow，再基于新的已保存版本运行。";
  if (!selectedCase.value) return "请先保存当前调试例。";
  if (caseDirty.value) return "请先保存调试例修改。";
  if (!draftValid.value) return "请选择当前步骤的直接下游节点。";
  if (debug.currentRun.value && ["starting", "running", "paused"].includes(debug.currentRun.value.status)) return "当前调试运行尚未结束。";
  return undefined;
});

onMounted(async () => {
  await debug.loadCases();
  const first = debug.cases.value[0];
  if (first) await selectCase(first);
});

function createCase(): void {
  selectedCaseId.value = null;
  draft.value = newWorkflowDebugCaseDraft(props.step, debug.cases.value.length);
  debug.clearRun();
}

async function selectCase(item: WorkflowDebugCase): Promise<void> {
  selectedCaseId.value = item.id;
  draft.value = workflowDebugCaseDraft(item);
  debug.clearRun();
  await debug.loadHistory(item.id);
}

async function saveCase(): Promise<void> {
  if (!draftValid.value) return;
  const saved = await debug.saveCase(workflowDebugCasePayload(draft.value), selectedCaseId.value ?? undefined);
  if (saved) {
    selectedCaseId.value = saved.id;
    draft.value = workflowDebugCaseDraft(saved);
  }
}

async function deleteCase(): Promise<void> {
  deleteOpen.value = false;
  if (!selectedCaseId.value || !await debug.deleteCase(selectedCaseId.value)) return;
  const first = debug.cases.value[0];
  if (first) await selectCase(first);
  else createCase();
}
</script>

<template>
  <Modal :open="props.open" :title="`单步调试 · ${props.step.name}`" :description="`基于已保存的 Workflow revision ${props.revision} 管理调试例和验证直接跳转。`" size="workspace" motion="workflow" @close="emit('close')">
    <div class="workflow-debug-shell">
      <div v-if="props.workflowDirty" class="workflow-debug-dirty-banner">Workflow 存在未保存修改。你仍可管理调试例和查看历史，但需要先保存才能发起运行。</div>
      <div v-if="debug.error.value" class="form-error workflow-debug-message">{{ debug.error.value }}</div>
      <div v-else-if="debug.notice.value" class="workflow-debug-notice">{{ debug.notice.value }}</div>
      <div class="workflow-debug-layout">
        <aside class="workflow-debug-case-list">
          <div class="workflow-debug-case-list-head"><div><h3>调试例</h3><span>{{ debug.cases.value.length }} 个</span></div><UiIconButton label="新建调试例" variant="secondary" size="sm" @click="createCase"><Plus /></UiIconButton></div>
          <div v-if="debug.loading.value" class="workflow-debug-list-state">正在加载调试例…</div>
          <nav v-else-if="debug.cases.value.length" aria-label="单步调试例">
            <button v-for="item in debug.cases.value" :key="item.id" type="button" :class="{ active: item.id === selectedCaseId }" @click="selectCase(item)"><strong>{{ item.name }}</strong><small>{{ item.description || "无说明" }}</small></button>
          </nav>
          <div v-else class="workflow-debug-list-state">尚未创建调试例。</div>
        </aside>

        <main class="workflow-debug-case-pane">
          <div class="workflow-debug-editor-head">
            <div><h3>{{ selectedCase ? "编辑调试例" : "新建调试例" }}</h3><p>输入值和采集信息均使用已保存文档中的稳定 ID。</p></div>
            <div class="workflow-debug-editor-actions">
              <UiIconButton v-if="selectedCase" label="删除调试例" variant="danger" :disabled="debug.deleting.value" @click="deleteOpen = true"><Trash2 /></UiIconButton>
              <UiButton variant="primary" :state="debug.saving.value ? 'loading' : 'idle'" :disabled="!draftValid || !caseDirty" :disabled-reason="!draftValid ? '请填写名称并选择直接下游节点。' : !caseDirty ? '当前调试例没有修改。' : undefined" loading-label="保存中" @click="saveCase">保存调试例</UiButton>
            </div>
          </div>
          <WorkflowDebugCaseEditor :bundle="props.bundle" :step="props.step" :draft="draft" :disabled="debug.saving.value" @change="draft = $event" />
        </main>

        <WorkflowDebugRunPanel
          :current-run="debug.currentRun.value"
          :history="debug.history.value"
          :next-cursor="debug.nextCursor.value"
          :start-disabled="Boolean(startDisabledReason)"
          :start-disabled-reason="startDisabledReason"
          :starting="debug.starting.value"
          :advancing="debug.advancing.value"
          :history-loading="debug.historyLoading.value"
          @start="selectedCase && debug.startRun(selectedCase.id)"
          @advance="debug.advanceRun()"
          @select="debug.selectRun"
          @more="selectedCase && debug.loadHistory(selectedCase.id, false)"
        />
      </div>
    </div>
  </Modal>
  <WorkflowConfirmModal v-if="selectedCase" :open="deleteOpen" title="删除调试例" description="该调试例和对应运行历史将被永久删除。" confirm-label="删除" tone="danger" @close="deleteOpen = false" @confirm="deleteCase" />
</template>
