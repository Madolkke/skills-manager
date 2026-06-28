<script setup lang="ts">
import { Play, RotateCcw } from "lucide-vue-next";
import OpencodeModelSelector from "./OpencodeModelSelector.vue";
import { actionBarStatusText, type RunnerSummary } from "../lib/evalRunner";
import type { OpencodeModelSelection, OpencodeProviderCatalog } from "../../../types";

defineProps<{
  busy: boolean;
  canRunFormal: boolean;
  caseCount: number;
  disabled?: boolean;
  modelCatalog: OpencodeProviderCatalog | null;
  modelError: string;
  modelLoading: boolean;
  modelSelection: OpencodeModelSelection | null;
  pollIntervalSeconds: number;
  summary: RunnerSummary;
}>();

defineEmits<{
  refreshModels: [];
  retryFailed: [];
  runAll: [];
  runFormal: [];
  selectModel: [selection: OpencodeModelSelection | null];
}>();
</script>

<template>
  <div class="runner-action-bar">
    <div class="runner-action-copy">
      <strong>执行测评</strong>
      <span>{{ actionBarStatusText(summary, caseCount, pollIntervalSeconds) }}</span>
    </div>
    <OpencodeModelSelector
      :catalog="modelCatalog"
      :error="modelError"
      :loading="modelLoading"
      :selection="modelSelection"
      @refresh="$emit('refreshModels')"
      @select="$emit('selectModel', $event)"
    />
    <div class="runner-action-buttons">
      <button class="secondary-button" type="button" :disabled="disabled || busy || caseCount === 0" @click="$emit('runAll')">
        <Play :size="17" />
        {{ busy ? "运行中..." : "运行全部" }}
      </button>
      <button class="secondary-button" type="button" :disabled="disabled || busy || summary.failedRuns === 0" @click="$emit('retryFailed')">
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
