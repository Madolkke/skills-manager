<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../../components/dropdown";
import type { EvalRunnerConfig } from "../../../types";

const providerOptions: DropdownSelectOption[] = [
  { value: "", label: "使用 Opencode 默认模型", description: "不指定服务商，由 Opencode 决定" },
  { value: "deepseek", label: "DeepSeek", description: "使用 DeepSeek 测试模型" },
];

const modelOptions: DropdownSelectOption[] = [
  { value: "", label: "使用默认模型", description: "跟随服务商或 Opencode 设置" },
  { value: "deepseek-v4-flash", label: "deepseek-v4-flash", description: "更快，适合常规回归测试" },
  { value: "deepseek-v4-pro", label: "deepseek-v4-pro", description: "能力更强，适合复杂场景" },
];

defineProps<{ open: boolean; notes: string; runnerConfig: EvalRunnerConfig }>();
const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:notes": [value: string];
  provider: [value: string];
  model: [value: string | null];
}>();
</script>

<template>
  <section class="scenario-advanced">
    <button class="scenario-advanced-toggle" type="button" @click="emit('update:open', !open)">
      <span>
        <strong>高级设置</strong>
        <small>模型和备注通常可以保持默认</small>
      </span>
      <ChevronDown :class="open && 'open'" :size="18" />
    </button>
    <div v-if="open" class="scenario-advanced-body">
      <div class="runner-config-grid">
        <label class="field-label">
          服务商
          <DropdownSelect :model-value="runnerConfig.model_provider_id ?? ''" :options="providerOptions" aria-label="选择服务商" @update:model-value="emit('provider', $event)" />
        </label>
        <label class="field-label">
          模型
          <DropdownSelect
            :model-value="runnerConfig.model_id ?? ''"
            :options="modelOptions"
            :disabled="!runnerConfig.model_provider_id"
            aria-label="选择模型"
            @update:model-value="emit('model', $event || null)"
          />
        </label>
      </div>
      <label class="field-label">
        备注
        <input :value="notes" placeholder="来源或维护说明，可选" @input="emit('update:notes', ($event.target as HTMLInputElement).value)">
      </label>
    </div>
  </section>
</template>
