<script setup lang="ts">
import { ArrowRight } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import Modal from "../../../../components/Modal.vue";
import UiButton from "../../../../components/ui/UiButton.vue";
import type { WorkflowBundle, WorkflowDebugCasePayload, WorkflowStep } from "../../../../types";
import { workflowDebugTargetName } from "../../debug/form";
import WorkflowDebugCaseEditor from "../../debug/components/WorkflowDebugCaseEditor.vue";

const props = defineProps<{
  open: boolean;
  bundle: WorkflowBundle;
  step: WorkflowStep;
  candidates: WorkflowDebugCasePayload[];
  selected: boolean[];
  proposalStatus: "proposed" | "applied" | "stale";
  disabled?: boolean;
  dirty?: boolean;
  canApply?: boolean;
}>();
const emit = defineEmits<{
  apply: [];
  change: [index: number, candidate: WorkflowDebugCasePayload];
  close: [];
  select: [index: number, selected: boolean];
}>();
const activeIndex = ref(0);
const activeCandidate = computed(() => props.candidates[activeIndex.value] ?? null);
const selectedCount = computed(() => props.selected.filter(Boolean).length);
const proposalState = computed(() => ({
  applied: { label: "已创建", tone: "success" },
  proposed: { label: "待确认", tone: "pending" },
  stale: { label: "已过期", tone: "warning" },
})[props.proposalStatus]);

watch(() => props.open, (open) => {
  if (open && !props.candidates[activeIndex.value]) activeIndex.value = 0;
});
</script>

<template>
  <Modal :open="props.open" size="workspace" motion="workflow" :title="`调试例候选 · ${props.step.name}`" @close="emit('close')">
    <template #description>
      <div class="workflow-agent-proposal-description">
        <span>{{ props.candidates.length }} 个候选来自当前 Agent 提案，确认后将以单个事务创建。</span>
        <strong :class="`is-${proposalState.tone}`">{{ proposalState.label }}</strong>
      </div>
    </template>
    <div class="workflow-agent-proposal-workspace">
      <div class="workflow-agent-proposal-layout">
        <aside class="workflow-agent-candidate-list">
          <header><div><strong>候选列表</strong><span>逐项检查并选择</span></div><b>{{ selectedCount }} / {{ props.candidates.length }}</b></header>
          <nav aria-label="Agent 调试例候选">
            <div v-for="(candidate, index) in props.candidates" :key="`${candidate.expected_target_id}-${index}`" :class="{ active: activeIndex === index, 'is-excluded': !props.selected[index] }">
              <input type="checkbox" :checked="props.selected[index]" :disabled="props.disabled" :aria-label="`选择候选：${candidate.name}`" @change="emit('select', index, ($event.target as HTMLInputElement).checked)" />
              <button type="button" :aria-current="activeIndex === index ? 'true' : undefined" @click="activeIndex = index">
                <span class="workflow-agent-candidate-index">{{ String(index + 1).padStart(2, "0") }}</span>
                <strong>{{ candidate.name }}</strong>
                <small><ArrowRight :size="12" />{{ workflowDebugTargetName(props.bundle, candidate.expected_target_id) }}</small>
              </button>
            </div>
          </nav>
        </aside>
        <main class="workflow-agent-candidate-editor">
          <header v-if="activeCandidate">
            <div><h3>{{ activeCandidate.name }}</h3><p><ArrowRight :size="13" />{{ workflowDebugTargetName(props.bundle, activeCandidate.expected_target_id) }}</p></div>
            <span>{{ activeIndex + 1 }} / {{ props.candidates.length }}</span>
          </header>
          <div v-if="activeCandidate && !props.selected[activeIndex]" class="workflow-agent-candidate-disabled">该候选未被选中，可继续查看，但不会创建为调试例。</div>
          <WorkflowDebugCaseEditor v-if="activeCandidate" section-headings :bundle="props.bundle" :step="props.step" :draft="activeCandidate" :disabled="props.disabled || !props.selected[activeIndex]" @change="emit('change', activeIndex, $event)" />
        </main>
      </div>
      <footer class="modal-actions workflow-agent-proposal-footer">
        <div class="workflow-agent-proposal-footer-state">
          <strong>{{ selectedCount }} / {{ props.candidates.length }} 已选择</strong>
          <span v-if="props.dirty" class="is-warning">保存当前 Workflow 后才能创建调试例。</span>
          <span v-else-if="props.proposalStatus === 'applied'" class="is-success">该提案已创建。</span>
          <span v-else-if="props.proposalStatus === 'stale'" class="is-warning">提案基于旧版 Workflow，已无法创建。</span>
          <span v-else>确认内容后创建所选候选。</span>
        </div>
        <div class="workflow-agent-proposal-footer-actions">
          <UiButton variant="secondary" @click="emit('close')">关闭</UiButton>
          <UiButton variant="primary" :disabled="!props.canApply" @click="emit('apply')">创建所选调试例</UiButton>
        </div>
      </footer>
    </div>
  </Modal>
</template>
