<script setup lang="ts">
import { Search, X } from "lucide-vue-next";
import { computed } from "vue";
import { rootTagGroups, selectedLeafTags, tagValuePathLabel } from "../../lib/tagCascades";
import { tagKey } from "../../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../../types";
import { sortTagGroups, type TagCountMap } from "./hubFilters";
import HubTagFacetBranch from "./HubTagFacetBranch.vue";

const props = defineProps<{
  query: string;
  tagGroups: TagGroup[];
  selectedTags: SkillTagPayload[];
  tagCounts: TagCountMap;
  loadingTags: boolean;
  tagError: string;
}>();

const emit = defineEmits<{
  "update:query": [value: string];
  "toggle-tag": [tag: SkillTagPayload];
  "clear-tags": [];
}>();

const visibleRoots = computed(() => rootTagGroups(sortTagGroups(props.tagGroups)).filter((group) => group.free_form || group.values.length > 0));
const selectedLabels = computed(() => selectedLeafTags(props.selectedTags, props.tagGroups).map((tag) => ({
  ...tag,
  label: leafTagLabel(tag),
  pathLabel: tagValuePathLabel(props.tagGroups, tag.group_id, tag.value),
})));

function leafTagLabel(tag: SkillTagPayload): string {
  const group = props.tagGroups.find((item) => item.id === tag.group_id);
  return group?.values.find((item) => item.value === tag.value)?.display_name || tag.value;
}

function toggleTag(tag: SkillTagPayload): void {
  emit("toggle-tag", { group_id: tag.group_id, value: tag.value });
}

</script>

<template>
  <aside class="hub-filter-panel" aria-label="Skill 筛选">
    <section class="hub-filter-section">
      <div class="hub-filter-heading">
        <span>搜索</span>
      </div>
      <label class="search-field hub-search-field">
        <Search :size="20" />
        <input :value="query" placeholder="搜索 Skill、owner、版本说明、Tag" aria-label="搜索 Skill" @input="emit('update:query', ($event.target as HTMLInputElement).value)" />
      </label>
    </section>

    <section class="hub-filter-section">
      <div class="hub-filter-heading">
        <span>Tag 过滤</span>
        <button v-if="selectedTags.length" class="hub-text-button" type="button" @click="emit('clear-tags')">清除</button>
      </div>
      <div class="hub-selected-tags">
        <span v-for="tag in selectedLabels" :key="tagKey(tag)" class="tag-chip editable" :title="tag.pathLabel">
          <span class="tag-chip-label">{{ tag.label }}</span>
          <button type="button" :aria-label="`移除 ${tag.pathLabel}`" @click="toggleTag(tag)">
            <X :size="13" />
          </button>
        </span>
        <span v-if="!selectedLabels.length" class="tag-chip muted">未选择 Tag</span>
      </div>
    </section>

    <section class="hub-filter-section">
      <div v-if="loadingTags" class="hub-tag-state">正在加载 Tag...</div>
      <div v-else-if="tagError" class="hub-tag-state danger">{{ tagError }}</div>
      <div v-else-if="!visibleRoots.length" class="hub-tag-state">还没有包含 Tag 的根级 Group。</div>
      <div v-else class="hub-tag-picker" aria-label="级联 Tag 过滤">
        <HubTagFacetBranch
          v-for="group in visibleRoots"
          :key="group.id"
          :group="group"
          :groups="tagGroups"
          :selected-tags="selectedTags"
          :tag-counts="tagCounts"
          @toggle="toggleTag"
        />
      </div>
    </section>
  </aside>
</template>
