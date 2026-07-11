<script setup lang="ts">
import { computed } from "vue";
import SkillTagPicker from "../../components/SkillTagPicker.vue";
import type { TagDiagnosticFocus } from "../../lib/tagCascades";
import type { SkillSummary, SkillTagPayload, TagGroup } from "../../types";

const props = defineProps<{
  skills: SkillSummary[];
  tagGroups: TagGroup[];
  tagDrafts: Record<string, SkillTagPayload[]>;
  focus?: TagDiagnosticFocus | null;
}>();

const emit = defineEmits<{
  updateDraft: [skillId: string, tags: SkillTagPayload[]];
  save: [skill: SkillSummary, tags?: SkillTagPayload[]];
  clearFocus: [];
}>();

const visibleSkills = computed(() => {
  if (!props.focus) return props.skills;
  const ids = new Set(props.focus.skillIds);
  return props.skills.filter((item) => ids.has(item.skill.id));
});

const focusText = computed(() => {
  if (!props.focus) return "";
  const group = props.tagGroups.find((item) => item.id === props.focus?.groupId);
  const issue = props.focus.kind === "orphaned" ? "路径失效" : "缺少条件必填";
  return `${group?.display_name ?? props.focus.groupId} · ${issue}`;
});
</script>

<template>
  <section class="primary-panel admin-card admin-skill-tags">
    <div class="panel-title-row">
      <div>
        <h2>Skill Tags</h2>
        <p>修改 Skill 绑定的结构化 Tag。Tag Group 和 Tag 值需要先在后台维护。</p>
      </div>
      <div class="button-row">
        <span :class="['tag-chip', focus ? 'warning' : 'muted']">{{ focus ? focusText : `${skills.length} 个 Skill` }}</span>
        <button v-if="focus" class="secondary-button" type="button" @click="emit('clearFocus')">查看全部</button>
      </div>
    </div>
    <div v-for="item in visibleSkills" :key="item.skill.id" :class="['admin-skill-row', { 'has-tag-issue': focus }]">
      <div>
        <strong>{{ item.skill.slug }}</strong>
        <small>{{ item.skill.id }}</small>
        <small v-if="focus" class="field-hint danger">{{ focus.kind === "orphaned" ? "存在路径失效 Tag" : "缺少当前路径要求的必填 Tag" }}</small>
      </div>
      <SkillTagPicker :value="tagDrafts[item.skill.id] ?? []" :groups="tagGroups" @change="emit('updateDraft', item.skill.id, $event)" @done="emit('save', item, $event)" />
    </div>
    <p v-if="!visibleSkills.length" class="field-help">{{ focus ? "没有匹配该诊断的 Skill。" : "还没有 Skill。" }}</p>
  </section>
</template>
