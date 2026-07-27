<script setup lang="ts">
import type { WorkflowSkillGenerator } from "../../../types";

const props = defineProps<{
  generators: WorkflowSkillGenerator[];
  modelValue: string;
  disabled?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <section class="workflow-generator-selector" aria-labelledby="workflow-generator-heading">
    <div class="workflow-sync-section-heading">
      <div>
        <span>Generator</span>
        <strong id="workflow-generator-heading">输出结构</strong>
      </div>
    </div>
    <div class="workflow-generator-segments" role="radiogroup" aria-label="选择 Generator">
      <button
        v-for="generator in props.generators"
        :key="generator.id"
        type="button"
        role="radio"
        :class="['workflow-generator-segment', generator.id === props.modelValue && 'active']"
        :aria-checked="generator.id === props.modelValue"
        :disabled="props.disabled"
        @click="emit('update:modelValue', generator.id)"
      >
        <strong>{{ generator.label }}</strong>
        <small>{{ generator.version }}</small>
      </button>
    </div>
  </section>
</template>
