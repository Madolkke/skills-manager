<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../../components/dropdown";
import type { OpencodeModelSelection, OpencodeProviderCatalog, OpencodeProviderOption } from "../../../types";

const props = defineProps<{
  catalog: OpencodeProviderCatalog | null;
  error: string;
  loading: boolean;
  selection: OpencodeModelSelection | null;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [selection: OpencodeModelSelection | null];
}>();

const defaultOption: DropdownSelectOption = {
  value: "",
  label: "使用 Opencode 默认配置",
  description: "不指定 provider/model",
};

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
  if (props.loading) return "正在读取 Opencode provider 配置...";
  if (props.error) return props.error;
  if (!providersWithActiveModels.value.length) return "未读取到可用 provider，可继续使用 Opencode 默认配置。";
  return "provider/model 来自 Opencode 配置；SkillHub 不保存密钥。";
});

onMounted(() => emit("refresh"));

watch([() => props.selection?.provider_id, () => props.catalog], ([providerId]) => {
  if (!providerId || !props.catalog) return;
  const provider = providersWithActiveModels.value.find((item) => item.id === providerId);
  if (!provider) {
    emit("select", null);
    return;
  }
  const selectedModel = activeModels(provider).find((model) => model.id === props.selection?.model_id);
  if (!selectedModel) emit("select", { provider_id: provider.id, model_id: defaultModelId(provider) });
});

function selectProvider(providerId: string): void {
  if (!providerId) {
    emit("select", null);
    return;
  }
  const provider = providersWithActiveModels.value.find((item) => item.id === providerId);
  if (!provider) return;
  emit("select", { provider_id: provider.id, model_id: defaultModelId(provider) });
}

function selectModel(modelId: string): void {
  if (!props.selection || !modelId) return;
  emit("select", { provider_id: props.selection.provider_id, model_id: modelId });
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
      <strong>运行模型</strong>
      <button class="hub-text-button" type="button" :disabled="loading" @click="emit('refresh')">刷新</button>
    </div>
    <div class="opencode-model-fields">
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
    <p :class="['opencode-model-helper', error && 'danger']">{{ helperText }}</p>
  </section>
</template>
