<script setup lang="ts">
const props = defineProps<{ modelValue: boolean; revision: number; disabled?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();
</script>

<template>
  <label :class="['workflow-sync-confirmation', props.modelValue && 'confirmed', props.disabled && 'disabled']">
    <input
      type="checkbox"
      :checked="props.modelValue"
      :disabled="props.disabled"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span><strong>确认同步此预览</strong><small>Workflow revision {{ props.revision }}</small></span>
  </label>
</template>
