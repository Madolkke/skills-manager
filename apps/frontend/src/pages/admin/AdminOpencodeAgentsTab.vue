<script setup lang="ts">
import { computed, ref } from "vue";
import { humanDate } from "../../lib/format";
import type { OpencodeAgent, OpencodeAgentPayload, OpencodeProviderCatalog } from "../../types";
import AdminOpencodeAgentFormModal from "./AdminOpencodeAgentFormModal.vue";

const props = defineProps<{
  agents: OpencodeAgent[];
  providers: OpencodeProviderCatalog | null;
  selectedAgentId: string;
}>();
const emit = defineEmits<{
  select: [agentId: string];
  refreshProviders: [];
  create: [payload: OpencodeAgentPayload];
  update: [agentId: string, payload: OpencodeAgentPayload];
  delete: [agent: OpencodeAgent];
}>();

const search = ref("");
const modalMode = ref<"create" | "edit" | null>(null);

const selectedAgent = computed(() => props.agents.find((agent) => agent.id === props.selectedAgentId) ?? props.agents[0] ?? null);
const filteredAgents = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return props.agents;
  return props.agents.filter((agent) =>
    [agent.id, agent.name, agent.description, agent.provider_id ?? "", agent.model_id ?? ""]
      .some((value) => value.toLowerCase().includes(keyword)),
  );
});
const permissionSummary = computed(() => {
  const agent = selectedAgent.value;
  if (!agent) return "";
  const enabled = Object.entries(agent.permission ?? {}).filter(([, value]) => value).map(([key]) => key);
  return enabled.length ? enabled.join(" / ") : "未开启工具";
});
const modelSummary = computed(() => {
  const agent = selectedAgent.value;
  if (!agent?.provider_id || !agent.model_id) return "不设置默认模型";
  return `${agent.provider_id}/${agent.model_id}`;
});

function createAgent(payload: OpencodeAgentPayload): void {
  emit("create", payload);
  modalMode.value = null;
}

function updateAgent(payload: OpencodeAgentPayload): void {
  if (!selectedAgent.value) return;
  emit("update", selectedAgent.value.id, payload);
  modalMode.value = null;
}
</script>

<template>
  <div class="admin-directory-layout opencode-agents-admin">
    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <div>
          <h2>Opencode Agents</h2>
          <p>{{ agents.length }} 个 Agent · 测评页只显示已启用 Agent</p>
        </div>
        <button class="primary-button" type="button" @click="modalMode = 'create'">新建 Agent</button>
      </div>

      <label class="field-label compact">
        <span>搜索 Agent</span>
        <input v-model="search" placeholder="输入 ID、名称、描述或模型" />
      </label>
      <label class="field-label compact">
        <span>选择 Agent</span>
        <select :value="selectedAgent?.id ?? ''" :disabled="!filteredAgents.length" @change="emit('select', ($event.target as HTMLSelectElement).value)">
          <option v-for="agent in filteredAgents" :key="agent.id" :value="agent.id">
            {{ agent.name }} · {{ agent.enabled ? "启用" : "禁用" }}
          </option>
        </select>
      </label>

      <div v-if="selectedAgent" class="admin-selected-summary">
        <strong>{{ selectedAgent.name }}</strong>
        <span>{{ selectedAgent.id }}</span>
        <p>{{ selectedAgent.description || "无描述" }}</p>
      </div>
      <template v-if="selectedAgent">
        <dl class="admin-detail-grid compact">
          <div>
            <dt>状态</dt>
            <dd>{{ selectedAgent.enabled ? "启用" : "禁用" }}</dd>
          </div>
          <div>
            <dt>默认模型</dt>
            <dd>{{ modelSummary }}</dd>
          </div>
          <div>
            <dt>工具权限</dt>
            <dd>{{ permissionSummary }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ humanDate(selectedAgent.created_at) }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ humanDate(selectedAgent.updated_at) }}</dd>
          </div>
          <div>
            <dt>创建者</dt>
            <dd>{{ selectedAgent.created_by || "-" }}</dd>
          </div>
        </dl>
        <div class="button-row">
          <button class="secondary-button" type="button" @click="modalMode = 'edit'">编辑 Agent</button>
          <button class="danger-button" type="button" @click="emit('delete', selectedAgent)">软删除</button>
        </div>
        <button class="hub-text-button" type="button" @click="emit('refreshProviders')">刷新 Provider/Model 列表</button>
      </template>
      <div v-else class="admin-selected-summary empty">
        <strong>暂无 Agent</strong>
        <p>创建并启用后，测评页可以选择这个 Agent。</p>
      </div>
      <p v-if="agents.length && !filteredAgents.length" class="field-help">没有匹配的 Agent。</p>
    </section>

    <section class="primary-panel admin-card">
      <template v-if="selectedAgent">
        <div class="panel-title-row compact">
          <div>
            <h3>Prompt 与步骤</h3>
            <p>运行时会物化为 <code>.opencode/agents/{{ selectedAgent.id }}.md</code>。</p>
          </div>
        </div>

        <div class="admin-readonly-block">
          <span>Prompt</span>
          <pre class="opencode-agent-prompt">{{ selectedAgent.prompt }}</pre>
        </div>
        <div class="admin-readonly-block">
          <span>Steps</span>
          <p v-if="!selectedAgent.steps.length">未配置步骤。</p>
          <ol v-else class="opencode-agent-steps">
            <li v-for="step in selectedAgent.steps" :key="step">{{ step }}</li>
          </ol>
        </div>
      </template>
      <p v-else class="field-help">还没有可检阅的 Agent。</p>
    </section>

    <AdminOpencodeAgentFormModal
      v-if="modalMode"
      :agent="modalMode === 'edit' ? selectedAgent : null"
      :providers="providers"
      @close="modalMode = null"
      @submit="modalMode === 'edit' ? updateAgent($event) : createAgent($event)"
    />
  </div>
</template>
