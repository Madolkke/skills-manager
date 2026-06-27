<script setup lang="ts">
import SkillTagPicker from "../../components/SkillTagPicker.vue";
import type { SkillTagPayload, TagGroup } from "../../types";

defineProps<{
  tags: SkillTagPayload[];
  tagGroups: TagGroup[];
  disabled: boolean;
}>();

const emit = defineEmits<{
  change: [tags: SkillTagPayload[]];
  done: [tags: SkillTagPayload[]];
}>();
</script>

<template>
  <section class="settings-section">
    <div class="settings-section-header">
      <div>
        <h3>Skill Tags</h3>
        <p>Tag 用于分类展示，也可以被后台授权策略引用。</p>
      </div>
    </div>
    <div v-if="disabled" class="settings-notice muted">你可以查看当前 Tag，但没有编辑权限。</div>
    <SkillTagPicker :value="tags" :groups="tagGroups" :disabled="disabled" @change="emit('change', $event)" @done="emit('done', $event)" />
  </section>
</template>
