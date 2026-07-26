<script setup lang="ts">
import { Search } from "lucide-vue-next";
import { computed, ref } from "vue";
import { childGroupsForValue, sortTagValues, tagGroupPathLabel } from "../../lib/tagCascades";
import { tagKey } from "../../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../../types";
import type { TagCountMap } from "./hubFilters";

defineOptions({ name: "HubTagFacetBranch" });

const props = defineProps<{
  group: TagGroup;
  groups: TagGroup[];
  selectedTags: SkillTagPayload[];
  tagCounts: TagCountMap;
  depth?: number;
}>();
const emit = defineEmits<{ toggle: [tag: SkillTagPayload] }>();
const query = ref("");
const selectedKeys = computed(() => new Set(props.selectedTags.map(tagKey)));
const pathLabel = computed(() => tagGroupPathLabel(props.groups, props.group.id));
const values = computed(() => {
  const sorted = sortTagValues(props.group);
  const keyword = query.value.trim().toLowerCase();
  if (!keyword) return sorted;
  return sorted.filter((value) => `${value.display_name ?? ""} ${value.value} ${value.description}`.toLowerCase().includes(keyword));
});

function isSelected(value: string): boolean {
  return selectedKeys.value.has(tagKey({ group_id: props.group.id, value }));
}

function count(value: string): number {
  return props.tagCounts[tagKey({ group_id: props.group.id, value })] ?? 0;
}
</script>

<template>
  <section :class="['hub-tag-facet', { nested: (depth ?? 0) > 0 }]" :aria-label="pathLabel">
    <header class="hub-tag-facet-head">
      <div>
        <strong>{{ group.display_name }}</strong>
        <small v-if="group.parent">{{ pathLabel }}</small>
      </div>
      <span>{{ selectedTags.filter((tag) => tag.group_id === group.id).length || "" }}</span>
    </header>

    <label v-if="group.values.length > 7" class="search-field hub-tag-value-search">
      <Search :size="15" />
      <input v-model="query" placeholder="搜索候选值" :aria-label="`搜索 ${group.display_name} 候选值`" />
    </label>

    <div class="hub-tag-facet-values">
      <div v-for="value in values" :key="value.value" class="hub-tag-facet-value">
        <label :class="['hub-tag-option', { active: isSelected(value.value), disabled: !isSelected(value.value) && count(value.value) === 0 }]">
          <input
            type="checkbox"
            :checked="isSelected(value.value)"
            :disabled="!isSelected(value.value) && count(value.value) === 0"
            @change="emit('toggle', { group_id: group.id, value: value.value })"
          />
          <span class="hub-tag-option-copy">
            <strong>{{ value.display_name || value.value }}</strong>
            <small v-if="value.display_name">{{ value.value }}</small>
          </span>
          <span class="hub-tag-option-count" :aria-label="`${count(value.value)} 个匹配 Skill`">{{ count(value.value) }}</span>
        </label>

        <div v-if="isSelected(value.value)" class="hub-tag-facet-children">
          <HubTagFacetBranch
            v-for="child in childGroupsForValue(groups, group.id, value.value)"
            :key="child.id"
            :group="child"
            :groups="groups"
            :selected-tags="selectedTags"
            :tag-counts="tagCounts"
            :depth="(depth ?? 0) + 1"
            @toggle="emit('toggle', $event)"
          />
        </div>
      </div>
      <p v-if="!values.length" class="hub-tag-empty">没有匹配的候选值。</p>
    </div>
  </section>
</template>
