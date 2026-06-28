<script setup lang="ts">
import { Search, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
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

const visibleGroups = computed(() => sortTagGroups(props.tagGroups).filter((group) => group.values.length > 0));
const openGroupId = ref("");
const openGroup = computed(() => visibleGroups.value.find((group) => group.id === openGroupId.value) ?? null);
const selectedKeys = computed(() => new Set(props.selectedTags.map(tagKey)));
const selectedLabels = computed(() => props.selectedTags.map((tag) => ({ ...tag, label: selectedTagLabel(tag, props.tagGroups) })));

watch(visibleGroups, (groups) => {
  if (!groups.some((group) => group.id === openGroupId.value)) openGroupId.value = "";
});

function toggleGroup(groupId: string): void {
  openGroupId.value = openGroupId.value === groupId ? "" : groupId;
}

function closeGroup(): void {
  openGroupId.value = "";
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
        <span v-for="tag in selectedLabels" :key="tagKey(tag)" class="tag-chip editable">
          {{ tag.label }}
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
          <div v-for="group in visibleGroups" :key="group.id" class="hub-tag-group-popover-host" @keydown="handleKeydown">
            <button
              class="hub-tag-group-button"
              :class="{ active: openGroup?.id === group.id }"
              type="button"
              :aria-expanded="openGroup?.id === group.id"
              @click="toggleGroup(group.id)"
            >
              <span>{{ group.display_name }}</span>
              <small v-if="selectedCountForGroup(group.id)">{{ selectedCountForGroup(group.id) }}</small>
            </button>
            <Transition name="hub-tag-popover">
              <div v-if="openGroup?.id === group.id" class="hub-tag-popover">
                <div class="hub-tag-popover-head">
                  <strong>{{ group.display_name }}</strong>
                  <button type="button" aria-label="关闭 Tag 列表" @click="closeGroup">
                    <X :size="14" />
                  </button>
                </div>
                <button
                  v-for="value in sortTagValues(group.values)"
                  :key="value.value"
                  class="hub-tag-option"
                  :class="{ active: selectedKeys.has(tagKey({ group_id: group.id, value: value.value })) }"
                  type="button"
                  @click="toggleTag({ group_id: group.id, value: value.value })"
                >
                  <span>{{ tagValueLabel(value) }}</span>
                  <small>{{ countFor(group.id, value) }}</small>
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </section>
  </aside>
</template>
