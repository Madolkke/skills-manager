<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../../components/dropdown";
import type { OpencodeAgentCatalog, OpencodeProviderCatalog, OpencodeProviderOption, OpencodeRunSelection } from "../../../types";

const props = defineProps<{
  agentCatalog: OpencodeAgentCatalog | null;
  agentError: string;
  agentLoading: boolean;
  catalog: OpencodeProviderCatalog | null;
  error: string;
  loading: boolean;
  selection: OpencodeRunSelection | null;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [selection: OpencodeRunSelection | null];
}>();

const defaultOption: DropdownSelectOption = {
  value: "",
  label: "使用 Opencode 默认模型",
  description: "不指定 provider/model",
};
const defaultAgentOption: DropdownSelectOption = {
  value: "",
  label: "使用 Opencode 默认 Agent",
  description: "不指定 SkillHub Agent",
};

const agentOptions = computed<DropdownSelectOption[]>(() => [
  defaultAgentOption,
  ...(props.agentCatalog?.agents ?? []).map((agent) => ({
    value: agent.id,
    label: agent.name,
    description: agent.description || agent.id,
  })),
]);
const providerOptions = computed<DropdownSelectOption[]>(() => [
  defaultOption,
  ...providersWithActiveModels.value.map((provider) => ({
    value: provider.id,
    label: provider.name,
    description: `${activeModels(provider).length} 个可用模型`,
  })),
]);

const activeProvider = computed(() => providersWithActiveModels.value.find((provider) => provider.id === props.selection?.provider_id) ?? null);
const modelOptions = computed<DropdownSelectOption[]>(() =>
  activeModels(activeProvider.value).map((model) => ({
    value: model.id,
    label: model.name,
    description: [model.family, model.status].filter(Boolean).join(" · "),
  })),
);
const providersWithActiveModels = computed(() => (props.catalog?.providers ?? []).filter((provider) => activeModels(provider).length > 0));
const modelDisabled = computed(() => !props.selection || modelOptions.value.length === 0);
const helperText = computed(() => {
  if (props.agentLoading || props.loading) return "正在读取 Opencode Agent 和 provider 配置...";
  if (props.agentError || props.error) return props.agentError || props.error;
  if (!providersWithActiveModels.value.length) return "未读取到可用 provider，可继续使用 Opencode 默认配置。";
  return "Agent 由 SkillHub 保存；provider/model 来自 Opencode 配置且优先覆盖 Agent 默认模型。";
});

onMounted(() => emit("refresh"));

watch([() => props.selection?.provider_id, () => props.catalog], ([providerId]) => {
  if (!providerId || !props.catalog) return;
  const provider = providersWithActiveModels.value.find((item) => item.id === providerId);
  if (!provider) {
    emitSelection({ provider_id: undefined, model_id: undefined });
    return;
  }
  const selectedModel = activeModels(provider).find((model) => model.id === props.selection?.model_id);
  if (!selectedModel) emitSelection({ provider_id: provider.id, model_id: defaultModelId(provider) });
});

function selectAgent(agentId: string): void {
  emitSelection({ agent_id: agentId || undefined });
}

function selectProvider(providerId: string): void {
  if (!providerId) {
    emitSelection({ provider_id: undefined, model_id: undefined });
    return;
  }
  const provider = providersWithActiveModels.value.find((item) => item.id === providerId);
  if (!provider) return;
  emitSelection({ provider_id: provider.id, model_id: defaultModelId(provider) });
}

function selectModel(modelId: string): void {
  if (!props.selection || !modelId) return;
  emitSelection({ provider_id: props.selection.provider_id, model_id: modelId });
}

function emitSelection(patch: OpencodeRunSelection): void {
  const next = normalizeSelection({ ...(props.selection ?? {}), ...patch });
  emit("select", next);
}

function normalizeSelection(selection: OpencodeRunSelection): OpencodeRunSelection | null {
  const next: OpencodeRunSelection = {};
  if (selection.agent_id) next.agent_id = selection.agent_id;
  if (selection.provider_id && selection.model_id) {
    next.provider_id = selection.provider_id;
    next.model_id = selection.model_id;
  }
  return next.agent_id || next.provider_id ? next : null;
}

function defaultModelId(provider: OpencodeProviderOption): string {
  const models = activeModels(provider);
  const configured = models.find((model) => model.id === provider.default_model_id);
  return (configured ?? models[0]).id;
}

function activeModels(provider?: OpencodeProviderOption | null) {
  return (provider?.models ?? []).filter((model) => !model.status || model.status === "active");
}
</script>

<template>
  <section class="opencode-model-selector">
    <div class="opencode-model-selector-head">
      <strong>运行配置</strong>
      <button class="hub-text-button" type="button" :disabled="loading || agentLoading" @click="emit('refresh')">刷新</button>
    </div>
    <div class="opencode-model-fields">
      <label class="field-label compact">
        <span>Agent</span>
        <DropdownSelect
          :model-value="selection?.agent_id ?? ''"
          :options="agentOptions"
          :disabled="agentLoading || Boolean(agentError)"
          aria-label="选择 Opencode Agent"
          compact
          @update:model-value="selectAgent"
        />
      </label>
      <label class="field-label compact">
        <span>Provider</span>
        <DropdownSelect
          :model-value="selection?.provider_id ?? ''"
          :options="providerOptions"
          :disabled="loading || Boolean(error)"
          aria-label="选择 Opencode provider"
          compact
          @update:model-value="selectProvider"
        />
      </label>
      <label class="field-label compact">
        <span>Model</span>
        <DropdownSelect
          :model-value="selection?.model_id ?? ''"
          :options="modelOptions"
          :disabled="modelDisabled"
          placeholder="先选择 Provider"
          aria-label="选择 Opencode model"
          compact
          @update:model-value="selectModel"
        />
      </label>
    </div>
    <p :class="['opencode-model-helper', (error || agentError) && 'danger']">{{ helperText }}</p>
  </section>
</template>
