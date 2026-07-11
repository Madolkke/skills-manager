<script setup lang="ts">
import { Search, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { activeTagGroups } from "../../lib/tagCascades";
import { tagKey } from "../../lib/skillTags";
import type { SkillTagPayload, TagGroup, TagValueOption } from "../../types";
import { selectedTagLabel, sortTagGroups, sortTagValues, tagValueLabel, type TagCountMap } from "./hubFilters";

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

const visibleGroupItems = computed(() => activeTagGroups(sortTagGroups(props.tagGroups), props.selectedTags).filter((item) => item.group.free_form || item.group.values.length > 0));
const visibleGroups = computed(() => visibleGroupItems.value.map((item) => item.group));
const openGroupId = ref("");
const openGroup = computed(() => visibleGroups.value.find((group) => group.id === openGroupId.value) ?? null);
const valueSearch = ref("");
const visibleValues = computed(() => {
  if (!openGroup.value) return [];
  const values = sortTagValues(openGroup.value.values);
  const keyword = valueSearch.value.trim().toLowerCase();
  if (!openGroup.value.free_form || !keyword) return values;
  return values.filter((value) => `${value.display_name ?? ""} ${value.value}`.toLowerCase().includes(keyword));
});
const selectedKeys = computed(() => new Set(props.selectedTags.map(tagKey)));
const selectedLabels = computed(() => props.selectedTags.map((tag) => ({ ...tag, label: selectedTagLabel(tag, props.tagGroups) })));

watch(visibleGroups, (groups) => {
  if (!groups.some((group) => group.id === openGroupId.value)) openGroupId.value = "";
});

function toggleGroup(groupId: string): void {
  openGroupId.value = openGroupId.value === groupId ? "" : groupId;
  valueSearch.value = "";
}

function closeGroup(): void {
  openGroupId.value = "";
  valueSearch.value = "";
}

function toggleTag(tag: SkillTagPayload): void {
  emit("toggle-tag", tag);
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    closeGroup();
    return;
  }
}

function countFor(groupId: string, value: TagValueOption): number {
  return props.tagCounts[tagKey({ group_id: groupId, value: value.value })] ?? 0;
}

function selectedCountForGroup(groupId: string): number {
  return props.selectedTags.filter((tag) => tag.group_id === groupId).length;
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
        <span v-for="tag in selectedLabels" :key="tagKey(tag)" class="tag-chip editable" :title="tag.label">
          <span class="tag-chip-label">{{ tag.label }}</span>
          <button type="button" :aria-label="`移除 ${tag.label}`" @click="emit('toggle-tag', tag)">
            <X :size="13" />
          </button>
        </span>
        <span v-if="!selectedLabels.length" class="tag-chip muted">未选择 Tag</span>
      </div>
    </section>

    <section class="hub-filter-section">
      <div v-if="loadingTags" class="hub-tag-state">正在加载 Tag...</div>
      <div v-else-if="tagError" class="hub-tag-state danger">{{ tagError }}</div>
      <div v-else-if="!visibleGroups.length" class="hub-tag-state">还没有包含 Tag 的 Tag Group。</div>
      <div v-else class="hub-tag-picker">
        <div class="hub-tag-group-buttons" aria-label="选择 Tag Group">
          <div v-for="item in visibleGroupItems" :key="item.group.id" class="hub-tag-group-popover-host" @keydown="handleKeydown">
            <button
              class="hub-tag-group-button"
              :class="{ active: openGroup?.id === item.group.id }"
              type="button"
              :aria-expanded="openGroup?.id === item.group.id"
              @click="toggleGroup(item.group.id)"
            >
              <span :title="item.group.display_name">{{ `${"  ".repeat(item.depth)}${item.depth ? "↳ " : ""}${item.group.display_name}` }}</span>
              <small v-if="selectedCountForGroup(item.group.id)">{{ selectedCountForGroup(item.group.id) }}</small>
            </button>
            <Transition name="hub-tag-popover">
              <div v-if="openGroup?.id === item.group.id" class="hub-tag-popover">
                <div class="hub-tag-popover-head">
                  <strong>{{ item.group.display_name }}</strong>
                  <button type="button" aria-label="关闭 Tag 列表" @click="closeGroup">
                    <X :size="14" />
                  </button>
                </div>
                <label v-if="item.group.free_form" class="search-field hub-tag-value-search">
                  <Search :size="15" />
                  <input v-model="valueSearch" placeholder="搜索候选值" aria-label="搜索自由 Tag 候选值" />
                </label>
                <button
                  v-for="value in visibleValues"
                  :key="value.value"
                  class="hub-tag-option"
                  :class="{ active: selectedKeys.has(tagKey({ group_id: item.group.id, value: value.value })) }"
                  type="button"
                  :title="value.value"
                  @click="toggleTag({ group_id: item.group.id, value: value.value })"
                >
                  <span>{{ tagValueLabel(value) }}</span>
                  <small>{{ countFor(item.group.id, value) }}</small>
                </button>
                <p v-if="!visibleValues.length" class="hub-tag-empty">没有匹配的候选值。</p>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </section>
  </aside>
</template>
