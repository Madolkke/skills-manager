<script setup lang="ts">
import { Play, RotateCcw } from "lucide-vue-next";
import { actionBarStatusText, type RunnerSummary } from "../lib/evalRunner";

defineProps<{
  busy: boolean;
  canAggregate: boolean;
  caseCount: number;
  pollIntervalSeconds: number;
  summary: RunnerSummary;
}>();

defineEmits<{
  aggregate: [];
  retryFailed: [];
  runAll: [];
}>();
</script>

<template>
  <div class="runner-action-bar">
    <span>{{ actionBarStatusText(summary, caseCount, pollIntervalSeconds) }}</span>
    <button class="secondary-button" type="button" :disabled="busy || caseCount === 0" @click="$emit('runAll')">
      <Play :size="17" />
      {{ busy ? "运行中..." : "运行全部" }}
    </button>
    <button class="secondary-button" type="button" :disabled="busy || summary.failedRuns === 0" @click="$emit('retryFailed')">
      <RotateCcw :size="17" />
      重试失败
    </button>
    <button class="primary-button" type="button" :disabled="!canAggregate" @click="$emit('aggregate')">
      <RotateCcw :size="17" />
      {{ busy ? "聚合中..." : "聚合 Opencode 测评结果" }}
    </button>
  </div>
</template>
