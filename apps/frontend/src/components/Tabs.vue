<script setup lang="ts">
import clsx from "clsx";
import { computed } from "vue";
import type { SkillTab } from "../lib/navigation";

const props = withDefaults(defineProps<{ active: SkillTab; hasWorkflow?: boolean }>(), { hasWorkflow: false });
const emit = defineEmits<{ change: [tab: SkillTab] }>();

const labels: Record<SkillTab, string> = {
  overview: "概览",
  workflow: "工作流",
  versions: "版本",
  evalsets: "测评集",
  evaluate: "测评",
  history: "历史",
  reviews: "评审",
  publish: "发布",
  settings: "设置",
};

const tabs = computed(() => (Object.keys(labels) as SkillTab[]).filter((tab) => tab !== "workflow" || props.hasWorkflow));
</script>

<template>
  <div class="skill-tabs" role="tablist" aria-label="Skill 页面">
    <button
      v-for="tab in tabs"
      :key="tab"
      :class="clsx('skill-tab', props.active === tab && 'active')"
      type="button"
      role="tab"
      :aria-selected="props.active === tab"
      @click="emit('change', tab)"
    >
      {{ labels[tab] }}
    </button>
  </div>
</template>
