<script setup lang="ts">
import { computed, ref, toRefs, watch } from "vue";
import { useListFilters } from "../../composables/useListFilters";
import PaginationBar from "../../components/PaginationBar.vue";
import { usePagedQuery } from "../../composables/usePagedQuery";
import { paginationApi } from "../../lib/api/paginationApi";
import { requiredTagMissingMessage, tagKey, toTagPayloads } from "../../lib/skillTags";
import SkillTagPicker from "../../components/SkillTagPicker.vue";
import { skillSecondaryName } from "../../lib/skillIdentity";
import type { TagDiagnosticFocus } from "../../lib/tagCascades";
import type { SkillSummary, SkillTagPayload, TagGroup } from "../../types";

const props = defineProps<{
  refreshToken?: number;
  tagGroups: TagGroup[];
  tagDrafts: Record<string, SkillTagPayload[]>;
  focus?: TagDiagnosticFocus | null;
}>();

const emit = defineEmits<{
  updateDraft: [skillId: string, tags: SkillTagPayload[]];
  save: [skill: SkillSummary, tags?: SkillTagPayload[]];
  clearFocus: [];
  discard: [skillId?: string];
}>();

const { query } = toRefs(useListFilters("admin-skills", { query: "" }));
const { page, pageSize, items: visibleSkills, total, loading, error, reload } = usePagedQuery("admin-skills",
  () => ({ query: query.value, diagnostic_group: props.focus?.groupId ?? null,
    diagnostic_kind: props.focus ? (props.focus.kind === "orphaned" ? "orphaned" : "missing_required") : null }),
  (params, signal) => paginationApi.skills(params, signal, true));
watch(() => props.refreshToken, () => void reload());
const dirtyCount = computed(() => Object.keys(props.tagDrafts).length);
const pickerGeneration = ref(0);
/** 丢弃同时重建当前编辑器，避免已展开的控件继续显示旧草稿。 */
function discard(skillId?: string) {
  emit("discard", skillId);
  pickerGeneration.value++;
}
/** 与服务端基线相同的选择不作为未保存草稿计数。 */
function updateDraft(item: SkillSummary, tags: SkillTagPayload[]) {
  const baseline = toTagPayloads(item.skill.tags).map(tagKey).sort();
  if (JSON.stringify(baseline) === JSON.stringify(tags.map(tagKey).sort())) emit("discard", item.skill.id);
  else emit("updateDraft", item.skill.id, tags);
}
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
        <span :class="['tag-chip', focus ? 'warning' : 'muted']">{{ focus ? focusText : `${total} 个 Skill` }}</span>
        <button v-if="focus" class="secondary-button" type="button" @click="emit('clearFocus')">查看全部</button>
      </div>
    </div>
    <input v-model="query" type="search" placeholder="搜索 Skill 名称或 slug" aria-label="搜索 Skill" />
    <p v-if="dirtyCount">{{ dirtyCount }} 个未保存草稿 <button type="button" class="secondary-button" @click="discard()">丢弃全部草稿</button></p>
    <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" :loading="loading" :error="error" @retry="reload" />
    <div v-for="item in visibleSkills" :key="item.skill.id" :class="['admin-skill-row', { 'has-tag-issue': focus }]">
      <div>
        <strong>{{ item.skill.slug }}</strong>
        <small v-if="skillSecondaryName(item.skill)">{{ skillSecondaryName(item.skill) }}</small>
        <small>{{ item.skill.id }}</small>
        <small v-if="focus" class="field-hint danger">{{ focus.kind === "orphaned" ? "存在路径失效 Tag" : "缺少当前路径要求的必填 Tag" }}</small>
      </div>
      <p v-if="tagDrafts[item.skill.id] && requiredTagMissingMessage(tagDrafts[item.skill.id], tagGroups)" class="field-hint danger">{{ requiredTagMissingMessage(tagDrafts[item.skill.id], tagGroups) }}</p>
      <p v-if="tagDrafts[item.skill.id]?.some(tag => !tagGroups.some(group => group.id === tag.group_id && group.values.some(value => value.value === tag.value)))" class="field-hint danger">草稿引用的 Tag 已不存在，请重新选择。</p>
      <SkillTagPicker :key="pickerGeneration" :value="tagDrafts[item.skill.id] ?? toTagPayloads(item.skill.tags)" :groups="tagGroups" @draft-change="updateDraft(item, $event)" @change="updateDraft(item, $event)" @done="emit('save', item, $event)" @cancel="discard(item.skill.id)" />
    </div>
    <p v-if="!loading && !error && !visibleSkills.length" class="field-help">{{ focus ? "没有匹配该诊断的 Skill。" : "还没有 Skill。" }}</p>
  </section>
</template>
