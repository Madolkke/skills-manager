<script setup lang="ts">
import clsx from "clsx";
import type { RunnerBoardItem } from "../lib/evalRunner";

defineProps<{ items: RunnerBoardItem[] }>();
</script>

<template>
  <div class="runner-status-board" aria-label="Opencode 任务状态">
    <div v-for="item in items" :key="item.kind" :class="clsx('runner-board-card', item.kind)">
      <span class="runner-status-dot" aria-hidden="true" />
      <strong>{{ item.count }}</strong>
      <small>{{ item.label }}</small>
    </div>
  </div>
</template>
