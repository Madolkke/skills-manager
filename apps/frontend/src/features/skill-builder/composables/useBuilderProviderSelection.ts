import { computed, ref } from "vue";
import type { OpencodeProviderCatalog, SkillBuilderRunSelection } from "../../../types";
import { activeBuilderProviders, builderModelOptions, builderProviderOptions, defaultBuilderModelId } from "../lib/builderUi";

export function useBuilderProviderSelection() {
  const providerCatalog = ref<OpencodeProviderCatalog | null>(null);
  const selection = ref<SkillBuilderRunSelection>({});
  const providersWithActiveModels = computed(() => activeBuilderProviders(providerCatalog.value?.providers ?? []));
  const providerOptions = computed(() => builderProviderOptions(providersWithActiveModels.value));
  const modelOptions = computed(() => builderModelOptions(providersWithActiveModels.value, selection.value.provider_id));

  function selectProvider(providerId: string): void {
    if (!providerId) {
      selection.value = {};
      return;
    }
    const provider = providersWithActiveModels.value.find((item) => item.id === providerId);
    if (!provider) return;
    selection.value = { provider_id: provider.id, model_id: defaultBuilderModelId(provider) };
  }

  function selectModel(modelId: string): void {
    if (!selection.value.provider_id || !modelId) return;
    selection.value = { ...selection.value, model_id: modelId };
  }

  return { providerCatalog, selection, providerOptions, modelOptions, selectProvider, selectModel };
}
