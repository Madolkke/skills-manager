<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";

defineProps<{ open: boolean; notes: string }>();
const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:notes": [value: string];
}>();
</script>

<template>
  <section class="scenario-advanced">
    <button class="scenario-advanced-toggle" type="button" @click="emit('update:open', !open)">
      <span>
        <strong>高级设置</strong>
        <small>Opencode 服务商和模型在 Opencode 侧配置</small>
      </span>
      <ChevronDown :class="open && 'open'" :size="18" />
    </button>
    <div v-if="open" class="scenario-advanced-body">
      <label class="field-label">
        备注
        <input :value="notes" placeholder="来源或维护说明，可选" @input="emit('update:notes', ($event.target as HTMLInputElement).value)">
      </label>
    </div>
  </section>
</template>
