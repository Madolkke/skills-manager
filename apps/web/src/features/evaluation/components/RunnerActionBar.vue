<script setup lang="ts">
import { Play, RotateCcw } from "lucide-vue-next";
import { actionBarStatusText, type RunnerSummary } from "../lib/evalRunner";

defineProps<{
  busy: boolean;
  canRunFormal: boolean;
  caseCount: number;
  pollIntervalSeconds: number;
  summary: RunnerSummary;
}>();

defineEmits<{
  retryFailed: [];
  runAll: [];
  runFormal: [];
}>();
</script>

<template>
  <div class="runner-action-bar">
    <div class="runner-action-copy">
      <strong>执行测评</strong>
      <span>{{ actionBarStatusText(summary, caseCount, pollIntervalSeconds) }}</span>
    </div>
    <div class="runner-action-buttons">
      <button class="secondary-button" type="button" :disabled="busy || caseCount === 0" @click="$emit('runAll')">
        <Play :size="17" />
        {{ busy ? "运行中..." : "运行全部" }}
      </button>
      <button class="secondary-button" type="button" :disabled="busy || summary.failedRuns === 0" @click="$emit('retryFailed')">
        <RotateCcw :size="17" />
        重试失败
      </button>
      <button class="primary-button" type="button" :disabled="!canRunFormal" @click="$emit('runFormal')">
        <RotateCcw :size="17" />
        {{ busy ? "正式测评中..." : "运行正式测评" }}
      </button>
    </div>
  </div>
</template>
