<script setup lang="ts">
import clsx from "clsx";
import { Grid2X2, List, Plus } from "lucide-vue-next";
import { computed, defineComponent, h, onMounted, ref } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../components/dropdown";
import { api } from "../lib/api";
import { tagKey } from "../lib/skillTags";
import HubFilterPanel from "./hub/HubFilterPanel.vue";
import HubSkillCard from "./hub/HubSkillCard.vue";
import { filterSkills, skillCounts, sortSkills, tagUsageCounts, type FilterKey, type SortKey, type ViewMode } from "./hub/hubFilters";
import type { SkillSummary, SkillTagPayload, TagGroup } from "../types";

const props = defineProps<{ skills: SkillSummary[]; actor: string; loading: boolean }>();
const emit = defineEmits<{ "open-skill": [skillId: string]; "open-workflows": []; create: [] }>();

const query = ref("");
const filter = ref<FilterKey>("all");
const sortKey = ref<SortKey>("updated");
const viewMode = ref<ViewMode>("list");
const tagGroups = ref<TagGroup[]>([]);
const selectedTags = ref<SkillTagPayload[]>([]);
const loadingTags = ref(false);
const tagError = ref("");

const sortOptions: DropdownSelectOption[] = [
  { value: "updated", label: "最近更新" },
  { value: "score", label: "验证得分" },
  { value: "name", label: "名称" },
];

const filtered = computed(() =>
  filterSkills(props.skills, {
    query: query.value,
    filter: filter.value,
    actor: props.actor,
    selectedTags: selectedTags.value,
    tagGroups: tagGroups.value,
  }),
);
const sorted = computed(() => sortSkills(filtered.value, sortKey.value));
const counts = computed(() => skillCounts(props.skills, props.actor));
const tagCounts = computed(() => tagUsageCounts(props.skills));

const FilterButton = defineComponent({
  props: {
    active: { type: Boolean, required: true },
    label: { type: String, required: true },
    count: { type: Number, required: true },
  },
  emits: ["click"],
  setup(buttonProps, { emit: componentEmit }) {
    return () =>
      h("button", { class: clsx("filter-button", buttonProps.active && "active"), type: "button", onClick: () => componentEmit("click") }, [
        buttonProps.label,
        h("span", buttonProps.count),
      ]);
  },
});

onMounted(() => {
  void loadTagGroups();
});

async function loadTagGroups(): Promise<void> {
  loadingTags.value = true;
  tagError.value = "";
  try {
    tagGroups.value = await api.listTagGroups();
  } catch (error) {
    tagError.value = error instanceof Error ? error.message : "Tag 加载失败。";
  } finally {
    loadingTags.value = false;
  }
}

function toggleTag(tag: SkillTagPayload): void {
  const key = tagKey(tag);
  if (selectedTags.value.some((item) => tagKey(item) === key)) {
    selectedTags.value = selectedTags.value.filter((item) => tagKey(item) !== key);
    return;
  }
  selectedTags.value = [...selectedTags.value, tag];
}
</script>

<template>
  <div class="hub-page">
    <HubFilterPanel
      v-model:query="query"
      :tag-groups="tagGroups"
      :selected-tags="selectedTags"
      :tag-counts="tagCounts"
      :loading-tags="loadingTags"
      :tag-error="tagError"
      @toggle-tag="toggleTag"
      @clear-tags="selectedTags = []"
    />

    <section class="hub-results-panel">
      <div class="hub-toolbar">
        <div class="filter-tabs">
          <FilterButton :active="filter === 'all'" label="全部" :count="counts.all" @click="filter = 'all'" />
          <FilterButton :active="filter === 'verified'" label="已验证" :count="counts.verified" @click="filter = 'verified'" />
          <FilterButton :active="filter === 'untested'" label="未测" :count="counts.untested" @click="filter = 'untested'" />
          <FilterButton :active="filter === 'mine'" label="我维护的" :count="counts.mine" @click="filter = 'mine'" />
        </div>
        <div class="view-tools">
          <label class="sort-control">
            <span>排序</span>
            <DropdownSelect v-model="sortKey" :options="sortOptions" aria-label="排序方式" compact />
          </label>
          <button
            :class="clsx('icon-button', viewMode === 'grid' && 'active')"
            type="button"
            aria-label="卡片视图"
            :aria-pressed="viewMode === 'grid'"
            @click="viewMode = 'grid'"
          >
            <Grid2X2 :size="19" />
          </button>
          <button
            :class="clsx('icon-button', viewMode === 'list' && 'active')"
            type="button"
            aria-label="列表视图"
            :aria-pressed="viewMode === 'list'"
            @click="viewMode = 'list'"
          >
            <List :size="19" />
          </button>
        </div>
      </div>

      <div v-if="loading" class="quiet-panel">正在加载 Skill...</div>
      <div v-else-if="sorted.length === 0" class="empty-state-panel">
        <strong>没有匹配的 Skill</strong>
        <p>换一个关键词或筛选条件，或新建一个标准 skill bundle 开始验证。</p>
        <button class="primary-button" type="button" @click="emit('create')">
          <Plus :size="17" />
          新建 Skill
        </button>
        <button class="secondary-button" type="button" @click="emit('open-workflows')">打开工作流编排</button>
      </div>
      <div v-else :class="clsx('skill-grid', viewMode === 'list' && 'list-view')">
        <HubSkillCard v-for="item in sorted" :key="item.skill.id" :item="item" @click="emit('open-skill', item.skill.id)" />
      </div>
    </section>
  </div>
</template>
