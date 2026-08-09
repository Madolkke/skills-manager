<script setup lang="ts">
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

watch(() => props.open, (open) => {
  if (open && !props.candidates[activeIndex.value]) activeIndex.value = 0;
});
</script>

<template>
  <Modal :open="props.open" size="workspace" motion="workflow" :title="`调试例候选 · ${props.step.name}`" :description="`${props.candidates.length} 个候选来自当前 Agent 提案；确认后会以单个事务创建所选调试例。`" @close="emit('close')">
    <div class="workflow-agent-proposal-workspace">
      <div class="workflow-agent-proposal-layout">
        <aside class="workflow-agent-candidate-list">
          <header><strong>候选列表</strong><span>{{ props.selected.filter(Boolean).length }}/{{ props.candidates.length }} 已选择</span></header>
          <nav aria-label="Agent 调试例候选">
            <div v-for="(candidate, index) in props.candidates" :key="`${candidate.expected_target_id}-${index}`" :class="{ active: activeIndex === index }">
              <input type="checkbox" :checked="props.selected[index]" :disabled="props.disabled" :aria-label="`选择候选：${candidate.name}`" @change="emit('select', index, ($event.target as HTMLInputElement).checked)" />
              <button type="button" @click="activeIndex = index"><strong>{{ candidate.name }}</strong><small>{{ workflowDebugTargetName(props.bundle, candidate.expected_target_id) }}</small></button>
            </div>
          </nav>
        </aside>
        <main class="workflow-agent-candidate-editor">
          <header v-if="activeCandidate"><div><h3>编辑候选</h3><p>调整输入、采集回显与预期目标后，再统一创建调试例。</p></div><span>{{ activeIndex + 1 }} / {{ props.candidates.length }}</span></header>
          <WorkflowDebugCaseEditor v-if="activeCandidate" :bundle="props.bundle" :step="props.step" :draft="activeCandidate" :disabled="props.disabled || !props.selected[activeIndex]" @change="emit('change', activeIndex, $event)" />
        </main>
      </div>
      <footer class="modal-actions workflow-agent-proposal-footer">
        <span v-if="props.dirty">保存当前 Workflow 后才能创建调试例。</span>
        <span v-else-if="props.proposalStatus === 'applied'">该提案已经创建为调试例。</span>
        <span v-else-if="props.proposalStatus === 'stale'">该提案基于旧版 Workflow，已无法创建。</span>
        <UiButton variant="secondary" @click="emit('close')">关闭</UiButton>
        <UiButton variant="primary" :disabled="!props.canApply" @click="emit('apply')">创建所选调试例</UiButton>
      </footer>
    </div>
  </Modal>
</template>
