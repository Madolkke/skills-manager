<script setup lang="ts">
import { ArrowRight, Database, FileJson, GitBranch } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowImportCandidate } from "../workflowTransfer";

const props = defineProps<{
  candidate: WorkflowImportCandidate;
  currentWorkflowName: string;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{ close: []; confirm: [] }>();
</script>

<template>
  <Modal
    open
    size="wide"
    motion="workflow"
    title="导入 Workflow"
    description="确认文件内容后，将其写入当前 Workflow。"
    @close="emit('close')"
  >
    <div class="workflow-import-body">
      <div class="workflow-import-file">
        <FileJson :size="20" />
        <div><strong>{{ props.candidate.fileName }}</strong><span>Workflow 可移植导入包</span></div>
      </div>

      <div class="workflow-import-route" aria-label="导入目标">
        <div><span>导入内容</span><strong>{{ props.candidate.workflowName }}</strong></div>
        <ArrowRight :size="18" />
        <div><span>覆盖目标</span><strong>{{ props.currentWorkflowName }}</strong></div>
      </div>

      <dl class="workflow-import-summary">
        <div><dt><GitBranch :size="15" />步骤</dt><dd>{{ props.candidate.stepCount }}</dd></div>
        <div><dt><GitBranch :size="15" />结论</dt><dd>{{ props.candidate.conclusionCount }}</dd></div>
        <div><dt><Database :size="15" />Collection</dt><dd>{{ props.candidate.collectionCount }}</dd></div>
      </dl>

      <div class="workflow-import-warning">
        当前已保存的 Workflow 将被覆盖并产生新 revision；包内 Collection 会创建为独立定义。重复导入会再次创建新的 Collection。
      </div>
      <div v-if="props.error" class="form-error" role="alert">{{ props.error }}</div>
    </div>
    <footer class="modal-actions workflow-import-actions">
      <UiButton variant="secondary" :disabled="props.busy" @click="emit('close')">取消</UiButton>
      <UiButton variant="primary" :state="props.busy ? 'loading' : 'idle'" loading-label="导入中" @click="emit('confirm')">确认导入</UiButton>
    </footer>
  </Modal>
</template>
