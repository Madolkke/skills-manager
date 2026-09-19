<script setup lang="ts">
import type { SkillCore } from "../lib/api/paginationApi";

import type { ToastState } from "../types";
import SkillAccessPanel from "./SkillAccessPanel.vue";

defineProps<{ skill: SkillCore }>();
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
