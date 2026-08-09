<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ArchiveRestore, Send, Square, Trash2 } from "lucide-vue-next";
import UiButton from "../../../../components/ui/UiButton.vue";
import UiIconButton from "../../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowStep } from "../../../../types";
import WorkflowConfirmModal from "../../components/WorkflowConfirmModal.vue";
import { cloneWorkflow } from "../../domain/utils";
import { shouldSendWorkflowAgentMessage } from "../composerKeyboard";
import { useWorkflowAgent } from "../useWorkflowAgent";
import WorkflowAgentProposalEditor from "./WorkflowAgentProposalEditor.vue";
import WorkflowAgentTimeline from "./WorkflowAgentTimeline.vue";
import { workflowAgentApi } from "../api";

const props = defineProps<{
  skillId: string;
  bundle: WorkflowBundle;
  revision: number;
  selection: WorkflowSelection;
  dirty: boolean;
  readonly: boolean;
}>();
const agent = useWorkflowAgent(() => props.skillId);
const agentId = ref("workflow_assistant");
const input = ref("");
const deleteOpen = ref(false);
const proposalOpen = ref(false);
const selectedStep = computed(() => {
  const selection = props.selection;
  if (selection.type !== "step") return null;
  return props.bundle.workflow.nodes.find((node): node is WorkflowStep => "stepType" in node && node.id === selection.id) ?? null;
});
const proposalStep = computed(() => {
  const id = agent.candidates.value[0]?.step_id;
  return props.bundle.workflow.nodes.find((node): node is WorkflowStep => "stepType" in node && node.id === id) ?? null;
});
const selectedDescriptor = computed(() => agent.catalog.value?.agents.find((item) => item.id === agentId.value));
const generatorBlocked = computed(() => selectedDescriptor.value?.proposal_kind === "debug_case_draft" && !selectedStep.value?.topology.length);
const canSend = computed(() => Boolean(input.value.trim() && agent.session.value && agent.catalog.value?.available && !agent.active.value && !agent.busy.value && !props.readonly && !generatorBlocked.value));
const canApply = computed(() => Boolean(agent.currentRun.value?.proposal?.status === "proposed" && agent.selectedCandidates.value.some(Boolean) && !props.dirty && !agent.busy.value));

onMounted(() => void agent.load());

async function send(): Promise<void> {
  if (!canSend.value) return;
  const content = input.value;
  input.value = "";
  await agent.start({
    agent_id: agentId.value,
    content,
    base_revision: props.revision,
    draft: cloneWorkflow(props.bundle),
    selection: props.selection,
  });
}

function openProposal(run: typeof agent.runs.value[number]): void {
  if (agent.currentRun.value?.id !== run.id) void agent.selectRun(run);
  proposalOpen.value = true;
}

async function applyProposal(): Promise<void> {
  await agent.apply();
  if (agent.currentRun.value?.proposal?.status === "applied") proposalOpen.value = false;
}

function handleComposerKeydown(event: KeyboardEvent): void {
  if (!shouldSendWorkflowAgentMessage(event)) return;
  event.preventDefault();
  void send();
}

async function newSession(): Promise<void> {
  if (!agent.session.value || agent.active.value) return;
  try {
    await workflowAgentApi.archiveSession(agent.session.value.id);
    agent.session.value = await workflowAgentApi.createSession(props.skillId);
    agent.runs.value = [];
    agent.currentRun.value = null;
    agent.events.value = [];
  } catch (caught) {
    agent.error.value = caught instanceof Error ? caught.message : "新建助手会话失败。";
  }
}

async function deleteSession(): Promise<void> {
  if (!agent.session.value) return;
  const id = agent.session.value.id;
  try {
    await workflowAgentApi.archiveSession(id);
    await workflowAgentApi.deleteSession(id);
    deleteOpen.value = false;
    agent.session.value = await workflowAgentApi.createSession(props.skillId);
    agent.runs.value = [];
    agent.currentRun.value = null;
    agent.events.value = [];
  } catch (caught) {
    agent.error.value = caught instanceof Error ? caught.message : "删除助手会话失败。";
  }
}
</script>

<template>
  <section class="workflow-agent-panel">
    <header class="workflow-agent-header">
      <label><span>助手</span><select v-model="agentId" :disabled="agent.active.value || agent.loading.value"><option v-for="item in agent.catalog.value?.agents ?? []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <div class="workflow-agent-session-actions">
        <UiIconButton label="新建会话" size="sm" variant="ghost" :disabled="Boolean(agent.active.value)" @click="newSession"><ArchiveRestore /></UiIconButton>
        <UiIconButton label="永久删除当前会话" size="sm" variant="ghost" :disabled="Boolean(agent.active.value)" @click="deleteOpen = true"><Trash2 /></UiIconButton>
      </div>
    </header>

    <div v-if="agent.loading.value" class="workflow-agent-state">正在加载助手…</div>
    <div v-else-if="agent.error.value" class="workflow-agent-state is-error">{{ agent.error.value }}</div>
    <template v-else>
      <div v-if="!agent.catalog.value?.available" class="workflow-agent-state is-warning">{{ agent.catalog.value?.unavailable_reason }}</div>
      <div class="workflow-agent-security">当前草稿及相关采集原始样例会发送给配置的外部模型 Provider；完整 thinking 和工具事件会被保存。</div>
      <WorkflowAgentTimeline :runs="agent.runs.value" :current-run="agent.currentRun.value" :events="agent.events.value" :agents="agent.catalog.value?.agents ?? []" @select="agent.selectRun" @proposal="openProposal" />
      <div v-if="agent.notice.value" class="workflow-agent-notice">{{ agent.notice.value }}</div>
    </template>

    <footer class="workflow-agent-composer">
      <textarea v-model="input" rows="3" maxlength="20000" :disabled="props.readonly || Boolean(agent.active.value)" :placeholder="generatorBlocked ? '请选择一个包含直接目标的 Step' : selectedDescriptor?.description" @keydown="handleComposerKeydown" />
      <div><small>Enter 发送 · Ctrl + Enter 换行</small><UiButton v-if="agent.active.value" size="sm" variant="secondary" :disabled="agent.busy.value" @click="agent.cancel"><template #icon><Square /></template>取消</UiButton><UiButton v-else size="sm" :disabled="!canSend" @click="send"><template #icon><Send /></template>发送</UiButton></div>
    </footer>
    <WorkflowAgentProposalEditor
      v-if="proposalStep && agent.currentRun.value?.proposal"
      :open="proposalOpen"
      :bundle="props.bundle"
      :step="proposalStep"
      :candidates="agent.candidates.value"
      :selected="agent.selectedCandidates.value"
      :proposal-status="agent.currentRun.value.proposal.status"
      :disabled="agent.busy.value || agent.currentRun.value.proposal.status !== 'proposed'"
      :dirty="props.dirty"
      :can-apply="canApply"
      @apply="applyProposal"
      @change="agent.updateCandidate"
      @close="proposalOpen = false"
      @select="(index, selected) => agent.selectedCandidates.value[index] = selected"
    />
    <WorkflowConfirmModal :open="deleteOpen" title="永久删除助手会话" description="会话、提案、完整 thinking、工具事件及 AgentScope 原生数据都将被永久删除。" confirm-label="永久删除" tone="danger" @close="deleteOpen = false" @confirm="deleteSession" />
  </section>
</template>
