<script setup lang="ts">
import type { SkillDetail, ToastState } from "../types";
import SkillAccessPanel from "./SkillAccessPanel.vue";

defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ refresh: []; toast: [toast: ToastState]; deleted: [] }>();
</script>

<template>
  <div class="settings-page">
    <SkillAccessPanel
      :skill="skill"
      @refresh="emit('refresh')"
      @toast="emit('toast', $event)"
      @deleted="emit('deleted')"
    />
  </div>
</template>
