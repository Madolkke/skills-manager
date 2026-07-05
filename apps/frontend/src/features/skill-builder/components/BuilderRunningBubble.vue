<script setup lang="ts">
import { computed, onUnmounted, ref } from "vue";
import { builderRunningElapsedLabel } from "../lib/builderUi";

const props = defineProps<{ startedAt?: string | null }>();

const now = ref(Date.now());
const timer = window.setInterval(() => {
  now.value = Date.now();
}, 1000);

const elapsedLabel = computed(() => builderRunningElapsedLabel(props.startedAt, now.value));

onUnmounted(() => {
  window.clearInterval(timer);
});
</script>

<template>
  <article class="builder-message assistant running" role="status" aria-live="polite">
    <strong>Skill 创建 Agent</strong>
    <div class="builder-thinking">
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
    </div>
    <p>Skill 创建 Agent 正在思考 · {{ elapsedLabel }}</p>
  </article>
</template>
