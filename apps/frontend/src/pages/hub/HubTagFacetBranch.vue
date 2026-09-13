<script setup lang="ts">
import { ChevronDown, Search } from "lucide-vue-next";
import { computed, ref } from "vue";
import { childGroupsForSelectedParent, sortTagValues, tagGroupPathLabel } from "../../lib/tagCascades";
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
const expanded = ref(true);
const selectedKeys = computed(() => new Set(props.selectedTags.map(tagKey)));
const pathLabel = computed(() => tagGroupPathLabel(props.groups, props.group.id));
const values = computed(() => {
  const sorted = sortTagValues(props.group);
  const keyword = query.value.trim().toLowerCase();
  if (!keyword) return sorted;
  return sorted.filter((value) => `${value.display_name ?? ""} ${value.value} ${value.description}`.toLowerCase().includes(keyword));
});
const selectedValues = computed(() => sortTagValues(props.group).filter((value) => isSelected(value.value)));
const selectedChildren = computed(() => {
  const selectedValues = new Set(props.selectedTags.filter((tag) => tag.group_id === props.group.id).map((tag) => tag.value));
  if (!selectedValues.size) return [];
  const children = [
    ...childGroupsForSelectedParent(props.groups, props.group.id),
    ...props.groups.filter((group) => group.parent?.group_id === props.group.id && group.parent?.activation_mode !== "parent_selected" && selectedValues.has(group.parent?.value ?? "")),
  ];
  return [...new Map(children.map((child) => [child.id, child])).values()].sort((left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name));
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
      <div class="hub-tag-facet-actions">
        <span>{{ selectedTags.filter((tag) => tag.group_id === group.id).length || "" }}</span>
        <button type="button" :aria-label="`${expanded ? '折叠' : '展开'} ${group.display_name}`" :aria-expanded="expanded" @click="expanded = !expanded"><ChevronDown :class="{ 'is-collapsed': !expanded }" :size="15" /></button>
      </div>
    </header>

    <template v-if="expanded && group.display_mode !== 'multi_select'">
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
        </div>
        <p v-if="!values.length" class="hub-tag-empty">没有匹配的候选值。</p>
      </div>
    </template>
    <details v-else-if="expanded" class="hub-tag-multi-select">
      <summary>{{ selectedValues.length ? `已选 ${selectedValues.length} 项` : '选择候选值' }}</summary>
      <div class="hub-tag-multi-select-menu">
        <label v-if="group.values.length > 7" class="search-field hub-tag-value-search"><Search :size="15" /><input v-model="query" placeholder="搜索候选值" :aria-label="`搜索 ${group.display_name} 候选值`" /></label>
        <label v-for="value in values" :key="value.value" :class="['hub-tag-option', { active: isSelected(value.value), disabled: !isSelected(value.value) && count(value.value) === 0 }]">
          <input type="checkbox" :checked="isSelected(value.value)" :disabled="!isSelected(value.value) && count(value.value) === 0" @change="emit('toggle', { group_id: group.id, value: value.value })" />
          <span class="hub-tag-option-copy"><strong>{{ value.display_name || value.value }}</strong><small v-if="value.display_name">{{ value.value }}</small></span>
          <span class="hub-tag-option-count">{{ count(value.value) }}</span>
        </label>
      </div>
    </details>
    <div v-if="expanded && selectedChildren.length" class="hub-tag-facet-children sibling-groups">
      <HubTagFacetBranch v-for="child in selectedChildren" :key="child.id" :group="child" :groups="groups" :selected-tags="selectedTags" :tag-counts="tagCounts" :depth="(depth ?? 0) + 1" @toggle="emit('toggle', $event)" />
    </div>
  </section>
</template>
