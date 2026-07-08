<script setup lang="ts">
import SkillTagPicker from "../../components/SkillTagPicker.vue";
import type { SkillSummary, SkillTagPayload, TagGroup } from "../../types";

defineProps<{
  skills: SkillSummary[];
  tagGroups: TagGroup[];
  tagDrafts: Record<string, SkillTagPayload[]>;
}>();

const emit = defineEmits<{
  updateDraft: [skillId: string, tags: SkillTagPayload[]];
  save: [skill: SkillSummary, tags?: SkillTagPayload[]];
}>();
</script>

<template>
  <section class="primary-panel admin-card admin-skill-tags">
    <div class="panel-title-row">
      <div>
        <h2>Skill Tags</h2>
        <p>修改 Skill 绑定的结构化 Tag。Tag Group 和 Tag 值需要先在后台维护。</p>
      </div>
      <span class="tag-chip muted">{{ skills.length }} 个 Skill</span>
    </div>
    <div v-for="item in skills" :key="item.skill.id" class="admin-skill-row">
      <div>
        <strong>{{ item.skill.slug }}</strong>
        <small>{{ item.skill.id }}</small>
      </div>
      <SkillTagPicker :value="tagDrafts[item.skill.id] ?? []" :groups="tagGroups" @change="emit('updateDraft', item.skill.id, $event)" @done="emit('save', item, $event)" />
    </div>
    <p v-if="!skills.length" class="field-help">还没有 Skill。</p>
  </section>
</template>
