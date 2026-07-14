<script setup lang="ts">
import SkillTagPicker from "../../../components/SkillTagPicker.vue";
import type { SkillTagPayload, TagGroup } from "../../../types";

const props = defineProps<{
  tags: SkillTagPayload[];
  groups: TagGroup[];
  disabled: boolean;
  error: string;
}>();
const emit = defineEmits<{
  change: [tags: SkillTagPayload[]];
  save: [tags: SkillTagPayload[]];
}>();
</script>

<template>
  <section class="workflow-metadata-tags">
    <div class="workflow-subhead">
      <div><h3>Skill Tags</h3><p>Tag 属于外层 Skill，用于分类、筛选和授权策略，需单独保存。</p></div>
    </div>
    <p v-if="props.error" class="field-hint danger">{{ props.error }}</p>
    <SkillTagPicker :value="props.tags" :groups="props.groups" :disabled="props.disabled" @change="emit('change', $event)" @done="emit('save', $event)" />
  </section>
</template>
