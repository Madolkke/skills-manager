<script setup lang="ts">
import TagInput from "./TagInput.vue";
import type { TagGroup } from "../types";

const props = defineProps<{ group: TagGroup; values: string[]; disabled?: boolean }>();
const emit = defineEmits<{ change: [values: string[]] }>();
</script>

<template>
  <div class="skill-tag-free-input">
    <TagInput
      :value="values"
      :suggestions="group.values.map((item) => item.value)"
      :disabled="disabled"
      placeholder="输入 Tag 后按 Enter 或逗号"
      @change="emit('change', $event)"
    />
    <p class="field-help">可输入新值，也可从已有候选中选择。新值保存后会成为全局候选。</p>
  </div>
</template>
