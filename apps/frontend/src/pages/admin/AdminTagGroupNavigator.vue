<script setup lang="ts">
import { AlertTriangle, Search } from "lucide-vue-next";
import { computed, ref } from "vue";
import { sortGroups, tagGroupPathInfo } from "../../lib/tagCascades";
import type { TagGroup } from "../../types";

const props = defineProps<{ groups: TagGroup[]; selectedGroupId: string }>();
const emit = defineEmits<{ select: [groupId: string] }>();
const query = ref("");
const options = computed(() => sortGroups(props.groups).map((group) => {
  const path = tagGroupPathInfo(props.groups, group.id);
  return { group, path: path.segments.map((segment) => segment.label).join(" / "), valid: path.valid };
}));
const visibleOptions = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  if (!keyword) return options.value;
  return options.value.filter(({ group, path }) => `${path} ${group.id} ${group.description}`.toLowerCase().includes(keyword));
});
</script>

<template>
  <div class="admin-tag-group-navigator">
    <label class="search-field admin-tag-group-search">
      <Search :size="16" />
      <input v-model="query" placeholder="搜索 Group 或级联路径" aria-label="搜索 Tag Group" />
    </label>
    <div class="admin-tag-group-options" role="listbox" aria-label="选择 Tag Group">
      <button
        v-for="option in visibleOptions"
        :key="option.group.id"
        :class="['admin-tag-group-option', { selected: option.group.id === selectedGroupId }]"
        type="button"
        role="option"
        :aria-selected="option.group.id === selectedGroupId"
        @click="emit('select', option.group.id)"
      >
        <strong>{{ option.group.display_name }}</strong>
        <span>{{ option.path }}</span>
        <small>{{ option.group.id }} · 排序 {{ option.group.sort_order }}<template v-if="!option.valid"> · 路径失效</template></small>
        <AlertTriangle v-if="!option.valid" :size="15" class="warning-icon" />
      </button>
      <p v-if="!visibleOptions.length" class="field-help">没有匹配的 Tag Group。</p>
    </div>
  </div>
</template>
