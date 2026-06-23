<script setup lang="ts">
import clsx from "clsx";
import type { SkillTab } from "../lib/navigation";

const props = defineProps<{ active: SkillTab }>();
const emit = defineEmits<{ change: [tab: SkillTab] }>();

const labels: Record<SkillTab, string> = {
  overview: "概览",
  versions: "版本",
  evalsets: "测评集",
  evaluate: "测评",
  history: "历史",
  settings: "设置",
};

const tabs = Object.keys(labels) as SkillTab[];
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
