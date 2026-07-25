<script setup lang="ts">
import { Workflow } from "lucide-vue-next";
import { computed } from "vue";
import { compactText, humanDate, versionName } from "../../lib/format";
import { skillSecondaryName } from "../../lib/skillIdentity";
import { tagLabel } from "../../lib/skillTags";
import type { SkillSummary } from "../../types";

const props = defineProps<{ item: SkillSummary }>();
const emit = defineEmits<{ click: []; workflow: [] }>();

const activeTags = computed(() => props.item.skill.tags.filter((tag) => tag.path_valid !== false));
const visibleTags = computed(() => activeTags.value.slice(0, 3));
const hiddenTags = computed(() => activeTags.value.slice(3));
const hiddenTagTitle = computed(() => hiddenTags.value.map((tag) => tagLabel(tag)).join("、"));
const secondaryName = computed(() => skillSecondaryName(props.item.skill));
</script>

<template>
  <article class="skill-card">
    <button class="skill-card-main" type="button" @click="emit('click')">
      <div class="card-body">
        <div class="card-context">
          <span>维护者 {{ item.skill.owner_ref }}</span>
          <span>更新 {{ humanDate(item.skill.updated_at) }}</span>
        </div>
        <div class="skill-card-head">
          <div class="skill-card-title">
            <span class="skill-card-title-copy">
              <h3>{{ item.skill.slug }}</h3>
              <small v-if="secondaryName">{{ secondaryName }}</small>
            </span>
            <span v-if="item.workflow" class="workflow-skill-badge"><Workflow :size="12" />Workflow</span>
          </div>
        </div>
        <p>{{ compactText(item.summary.current_version?.description, "尚未填写 Skill 描述。") }}</p>
      </div>
      <div class="card-metrics">
        <span class="card-tag-cell">
          <small>Tag</small>
          <span class="card-tag-list">
            <span v-for="tag in visibleTags" :key="`${tag.group_id}:${tag.value}`" class="tag-chip" :title="tagLabel(tag)">
              <span class="tag-chip-label">{{ tagLabel(tag) }}</span>
            </span>
            <span v-if="!activeTags.length" class="tag-chip muted">未设置 Tag</span>
            <span
              v-if="hiddenTags.length"
              class="tag-chip tag-overflow"
              :title="hiddenTagTitle"
              :aria-label="`还有 ${hiddenTags.length} 个 Tag：${hiddenTagTitle}`"
            >+{{ hiddenTags.length }}</span>
          </span>
        </span>
        <span class="metric-cell version-metric-cell">
          <small>当前版本</small>
          <strong>{{ versionName(item.summary.current_version) }}</strong>
        </span>
      </div>
    </button>
    <button v-if="item.workflow" class="workflow-card-action" type="button" @click="emit('workflow')"><Workflow :size="15" />打开工作流</button>
  </article>
</template>
