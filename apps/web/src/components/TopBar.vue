<script setup lang="ts">
import { Plus, Settings, Workflow } from "lucide-vue-next";
import { onBeforeUnmount, ref, watch } from "vue";
import { slugTitle } from "../lib/format";
import type { SkillDetail } from "../types";

const props = withDefaults(defineProps<{ actor?: string; currentSkill?: SkillDetail | null }>(), {
  actor: "product-operator",
  currentSkill: null,
});
const emit = defineEmits<{ home: []; create: []; workflows: [] }>();

const menuOpen = ref(false);
const menuRef = ref<HTMLDivElement | null>(null);

watch(menuOpen, (open) => {
  if (open) document.addEventListener("mousedown", handleClick);
  else document.removeEventListener("mousedown", handleClick);
});

onBeforeUnmount(() => document.removeEventListener("mousedown", handleClick));

function handleClick(event: MouseEvent): void {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) menuOpen.value = false;
}
</script>

<template>
  <header class="top-bar">
    <button class="breadcrumb-root" type="button" @click="emit('home')">SkillHub</button>
    <template v-if="currentSkill">
      <span class="breadcrumb-separator">/</span>
      <strong class="breadcrumb-current">{{ slugTitle(currentSkill.skill.slug) }}</strong>
    </template>
    <div class="top-spacer" />
    <div class="top-bar-actions">
      <button class="secondary-button" type="button" @click="emit('workflows')">
        <Workflow :size="16" />
        工作流编排
      </button>
      <button class="primary-button" type="button" @click="emit('create')">
        <Plus :size="16" />
        新建 Skill
      </button>
    </div>
    <div ref="menuRef" class="actor-menu">
      <button
        class="actor-dot"
        type="button"
        :title="props.actor"
        :aria-label="`当前操作者 ${props.actor}`"
        @click="menuOpen = !menuOpen"
      >
        {{ props.actor.slice(0, 1).toUpperCase() }}
      </button>
      <div v-if="menuOpen" class="actor-dropdown">
        <div class="actor-dropdown-header">{{ props.actor }}</div>
        <button class="actor-dropdown-item" type="button" @click="menuOpen = false">
          <Settings :size="15" />
          设置
        </button>
      </div>
    </div>
  </header>
</template>
