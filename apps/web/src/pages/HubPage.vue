<script setup lang="ts">
import clsx from "clsx";
import { CheckCircle2, Circle, Grid2X2, List, Plus, Search } from "lucide-vue-next";
import { computed, defineComponent, h, ref, type PropType } from "vue";
import { humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../lib/format";
import type { SkillSummary } from "../types";

type FilterKey = "all" | "verified" | "untested" | "mine";
type SortKey = "updated" | "score" | "name";
type ViewMode = "grid" | "list";

const props = defineProps<{ skills: SkillSummary[]; actor: string; loading: boolean }>();
const emit = defineEmits<{ "open-skill": [skillId: string]; "open-workflows": []; create: [] }>();

const query = ref("");
const filter = ref<FilterKey>("all");
const sortKey = ref<SortKey>("updated");
const viewMode = ref<ViewMode>("grid");
const filtered = computed(() => filterSkills(props.skills, query.value, filter.value, props.actor));
const sorted = computed(() => sortSkills(filtered.value, sortKey.value));
const counts = computed(() => skillCounts(props.skills, props.actor));

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

const SkillCard = defineComponent({
  props: {
    item: { type: Object as PropType<SkillSummary>, required: true },
  },
  emits: ["click"],
  setup(cardProps, { emit: componentEmit }) {
    return () => {
      const run = cardProps.item.summary.latest_accepted_eval_run;
      const version = cardProps.item.summary.current_version;
      const status = scoreKind(run);
      return h("button", { class: "skill-card", type: "button", onClick: () => componentEmit("click") }, [
        h("div", { class: "card-body" }, [
          h("div", { class: "card-context" }, [
            h("span", `维护者 ${cardProps.item.skill.owner_ref}`),
            h("span", `更新 ${humanDate(cardProps.item.skill.updated_at)}`),
          ]),
          h("div", { class: "skill-card-head" }, [
            h("h3", slugTitle(cardProps.item.skill.slug)),
            h("span", { class: clsx("score-chip", status) }, scoreLabel(run)),
          ]),
          h("p", version?.change_summary ?? "尚未写入说明。"),
        ]),
        h("div", { class: "card-metrics" }, [
          h(Metric, { label: "验证得分", value: scoreLabel(run), tone: status }),
          h(Metric, { label: "测评集", value: cardProps.item.summary.primary_eval_set?.name ?? "未创建" }),
          h(Metric, { label: "当前版本", value: versionName(version) }),
          status === "empty" ? h(Circle, { class: "status-ring empty", size: 23 }) : h(CheckCircle2, { class: "status-ring verified", size: 23 }),
        ]),
      ]);
    };
  },
});

const Metric = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    tone: { type: String, default: undefined },
  },
  setup(metricProps) {
    return () => h("span", { class: "metric-cell" }, [h("small", metricProps.label), h("strong", { class: metricProps.tone }, metricProps.value)]);
  },
});

function filterSkills(skills: SkillSummary[], value: string, key: FilterKey, actor: string): SkillSummary[] {
  const normalized = value.trim().toLowerCase();
  return skills.filter((item) => {
    const text = [item.skill.slug, item.skill.owner_ref, item.summary.current_version?.change_summary, item.summary.current_version?.content_digest].join(" ").toLowerCase();
    if (normalized && !text.includes(normalized)) return false;
    if (key === "verified") return scoreKind(item.summary.latest_accepted_eval_run) !== "empty";
    if (key === "untested") return scoreKind(item.summary.latest_accepted_eval_run) === "empty";
    if (key === "mine") return item.skill.owner_ref === actor;
    return true;
  });
}

function skillCounts(skills: SkillSummary[], actor: string) {
  return {
    all: skills.length,
    verified: skills.filter((item) => scoreKind(item.summary.latest_accepted_eval_run) !== "empty").length,
    untested: skills.filter((item) => scoreKind(item.summary.latest_accepted_eval_run) === "empty").length,
    mine: skills.filter((item) => item.skill.owner_ref === actor).length,
  };
}

function sortSkills(skills: SkillSummary[], key: SortKey): SkillSummary[] {
  const copy = [...skills];
  if (key === "name") return copy.sort((left, right) => left.skill.slug.localeCompare(right.skill.slug));
  if (key === "score") return copy.sort((left, right) => scoreValue(right) - scoreValue(left) || updatedTime(right) - updatedTime(left));
  return copy.sort((left, right) => updatedTime(right) - updatedTime(left));
}

function scoreValue(item: SkillSummary): number {
  const run = item.summary.latest_accepted_eval_run;
  if (!run?.summary?.total) return -1;
  return ((run.summary.passed ?? 0) / run.summary.total) * 100;
}

function updatedTime(item: SkillSummary): number {
  const dates = [item.skill.updated_at, item.summary.current_version?.created_at, item.summary.latest_accepted_eval_run?.created_at]
    .map((date) => Date.parse(date ?? ""))
    .filter(Number.isFinite);
  return dates.length ? Math.max(...dates) : 0;
}
</script>

<template>
  <div class="hub-page">
    <section class="hub-main">
      <header class="hub-hero" />

      <label class="search-field">
        <Search :size="22" />
        <input v-model="query" placeholder="搜索 skill、owner、版本说明" aria-label="搜索 Skill" />
      </label>

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
            <select v-model="sortKey">
              <option value="updated">最近更新</option>
              <option value="score">验证得分</option>
              <option value="name">名称</option>
            </select>
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
        <p>换一个关键词，或新建一个标准 skill bundle 开始验证。</p>
        <button class="primary-button" type="button" @click="emit('create')">
          <Plus :size="17" />
          新建 Skill
        </button>
        <button class="secondary-button" type="button" @click="emit('open-workflows')">打开工作流编排</button>
      </div>
      <div v-else :class="clsx('skill-grid', viewMode === 'list' && 'list-view')">
        <SkillCard v-for="item in sorted" :key="item.skill.id" :item="item" @click="emit('open-skill', item.skill.id)" />
      </div>
    </section>
  </div>
</template>
