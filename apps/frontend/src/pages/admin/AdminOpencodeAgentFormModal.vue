<script setup lang="ts">
import { computed, ref } from "vue";
import DropdownSelect from "../../components/DropdownSelect.vue";
import Modal from "../../components/Modal.vue";
import type { DropdownSelectOption } from "../../components/dropdown";
import type { OpencodeAgent, OpencodeAgentPayload, OpencodeAgentPermission, OpencodeProviderCatalog, OpencodeProviderOption } from "../../types";

const props = defineProps<{
  agent?: OpencodeAgent | null;
  providers: OpencodeProviderCatalog | null;
}>();
const emit = defineEmits<{
  close: [];
  submit: [payload: OpencodeAgentPayload];
}>();

const tools: Array<{ key: keyof OpencodeAgentPermission; label: string }> = [
  { key: "bash", label: "Bash" },
  { key: "edit", label: "Edit" },
  { key: "glob", label: "Glob" },
  { key: "grep", label: "Grep" },
  { key: "list", label: "List" },
  { key: "read", label: "Read" },
  { key: "write", label: "Write" },
];

const id = ref(props.agent?.id ?? "");
const name = ref(props.agent?.name ?? "");
const description = ref(props.agent?.description ?? "");
const prompt = ref(props.agent?.prompt ?? "");
const enabled = ref(props.agent?.enabled ?? true);
const permission = ref<OpencodeAgentPermission>({ ...defaultPermission(), ...(props.agent?.permission ?? {}) });
const providerId = ref(props.agent?.provider_id ?? "");
const modelId = ref(props.agent?.model_id ?? "");
const temperature = ref(props.agent?.temperature == null ? "" : String(props.agent.temperature));
const stepsText = ref((props.agent?.steps ?? []).join("\n"));

const providerOptions = computed<DropdownSelectOption[]>(() => [
  { value: "", label: "不设置默认模型", description: "运行时使用 Opencode 默认配置或测评页显式选择" },
  ...providersWithActiveModels.value.map((provider) => ({
    value: provider.id,
    label: provider.name,
    description: `${activeModels(provider).length} 个可用模型`,
  })),
]);
const activeProvider = computed(() => providersWithActiveModels.value.find((provider) => provider.id === providerId.value) ?? null);
const modelOptions = computed<DropdownSelectOption[]>(() =>
  activeModels(activeProvider.value).map((model) => ({
    value: model.id,
    label: model.name,
    description: [model.family, model.status].filter(Boolean).join(" · "),
  })),
);
const providersWithActiveModels = computed(() => (props.providers?.providers ?? []).filter((provider) => activeModels(provider).length > 0));
const formError = computed(() => {
  if (!props.agent && !id.value.trim()) return "请填写 Agent ID。";
  if (!name.value.trim()) return "请填写名称。";
  if (!prompt.value.trim()) return "请填写 Prompt。";
  if (providerId.value && !modelId.value) return "设置默认 Provider 时需要选择 Model。";
  const temperatureValue = temperature.value.trim();
  if (temperatureValue) {
    const number = Number(temperatureValue);
    if (!Number.isFinite(number) || number < 0 || number > 2) return "Temperature 需要是 0 到 2 之间的数字。";
  }
  return "";
});

function selectProvider(nextProviderId: string): void {
  providerId.value = nextProviderId;
  if (!nextProviderId) {
    modelId.value = "";
    return;
  }
  const provider = providersWithActiveModels.value.find((item) => item.id === nextProviderId);
  modelId.value = provider ? defaultModelId(provider) : "";
}

function submit(): void {
  if (formError.value) return;
  const payload: OpencodeAgentPayload = {
    name: name.value.trim(),
    description: description.value.trim(),
    prompt: prompt.value.trim(),
    enabled: enabled.value,
    permission: { ...permission.value },
    provider_id: providerId.value || null,
    model_id: modelId.value || null,
    temperature: temperature.value.trim() ? Number(temperature.value.trim()) : null,
    steps: stepsText.value.split("\n").map((item) => item.trim()).filter(Boolean),
  };
  if (!props.agent) payload.id = id.value.trim();
  emit("submit", payload);
}

function defaultPermission(): OpencodeAgentPermission {
  return { bash: false, edit: false, glob: false, grep: false, list: false, read: false, write: false };
}

function defaultModelId(provider: OpencodeProviderOption): string {
  const models = activeModels(provider);
  const configured = models.find((model) => model.id === provider.default_model_id);
  return (configured ?? models[0])?.id ?? "";
}

function activeModels(provider?: OpencodeProviderOption | null) {
  return (provider?.models ?? []).filter((model) => !model.status || model.status === "active");
}
</script>

<template>
  <Modal :title="agent ? '编辑 Opencode Agent' : '新建 Opencode Agent'" size="wide" @close="emit('close')">
    <form class="admin-modal-form opencode-agent-form" @submit.prevent="submit">
      <div class="admin-form-grid">
        <label v-if="!agent" class="field-label">
          <span>Agent ID</span>
          <input v-model="id" placeholder="agent-default" />
        </label>
        <label class="field-label">
          <span>名称</span>
          <input v-model="name" placeholder="代码评审 Agent" />
        </label>
      </div>

      <label class="field-label">
        <span>描述</span>
        <input v-model="description" placeholder="用于测评页识别这个 Agent 的用途" />
      </label>

      <label class="field-label">
        <span>Prompt Markdown</span>
        <textarea v-model="prompt" rows="10" placeholder="写入 Opencode Agent 的系统提示词" />
      </label>

      <section class="opencode-agent-form-section">
        <div>
          <strong>工具权限</strong>
          <span>未开启的工具会在 Agent frontmatter 中标记为 false。</span>
        </div>
        <div class="opencode-agent-permissions">
          <label v-for="tool in tools" :key="tool.key" class="checkbox-line">
            <input v-model="permission[tool.key]" type="checkbox" />
            <span>{{ tool.label }}</span>
          </label>
        </div>
      </section>

      <div class="admin-form-grid">
        <label class="field-label compact">
          <span>默认 Provider</span>
          <DropdownSelect
            :model-value="providerId"
            :options="providerOptions"
            aria-label="选择 Agent 默认 Provider"
            @update:model-value="selectProvider"
          />
        </label>
        <label class="field-label compact">
          <span>默认 Model</span>
          <DropdownSelect
            v-model="modelId"
            :options="modelOptions"
            :disabled="!providerId"
            placeholder="先选择 Provider"
            aria-label="选择 Agent 默认 Model"
          />
        </label>
      </div>

      <div class="admin-form-grid">
        <label class="field-label">
          <span>Temperature</span>
          <input v-model="temperature" inputmode="decimal" placeholder="可为空，范围 0-2" />
        </label>
        <label class="switch-line opencode-agent-enabled">
          <input v-model="enabled" type="checkbox" />
          <span>{{ enabled ? "启用" : "禁用" }}</span>
        </label>
      </div>

      <label class="field-label">
        <span>Steps</span>
        <textarea v-model="stepsText" rows="4" placeholder="每行一个可选步骤" />
      </label>

      <p v-if="formError" class="field-help danger">{{ formError }}</p>
      <footer class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="submit" :disabled="Boolean(formError)">保存 Agent</button>
      </footer>
    </form>
  </Modal>
</template>
