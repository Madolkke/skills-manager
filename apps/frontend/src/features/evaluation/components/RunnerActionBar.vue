<script setup lang="ts">
import { Play, RotateCcw } from "lucide-vue-next";
import OpencodeModelSelector from "./OpencodeModelSelector.vue";
import { actionBarStatusText, type RunnerSummary } from "../lib/evalRunner";
import type { OpencodeAgentCatalog, OpencodeProviderCatalog, OpencodeRunSelection } from "../../../types";

defineProps<{
  busy: boolean;
  canRunFormal: boolean;
  caseCount: number;
  disabled?: boolean;
  disabledReason?: string;
  formalDisabledReason?: string;
  agentCatalog: OpencodeAgentCatalog | null;
  agentError: string;
  agentLoading: boolean;
  modelCatalog: OpencodeProviderCatalog | null;
  modelError: string;
  modelLoading: boolean;
  runSelection: OpencodeRunSelection | null;
  pollIntervalSeconds: number;
  summary: RunnerSummary;
}>();

defineEmits<{
  refreshModels: [];
  retryFailed: [];
  runAll: [];
  runFormal: [];
  selectRunConfig: [selection: OpencodeRunSelection | null];
}>();
</script>

<template>
  <div class="runner-action-bar">
    <div class="runner-action-copy">
      <strong>执行测评</strong>
      <span>{{ actionBarStatusText(summary, caseCount, pollIntervalSeconds) }}</span>
      <small v-if="disabledReason || formalDisabledReason" class="runner-disabled-reason">{{ disabledReason || formalDisabledReason }}</small>
    </div>
    <OpencodeModelSelector
      :agent-catalog="agentCatalog"
      :agent-error="agentError"
      :agent-loading="agentLoading"
      :catalog="modelCatalog"
      :error="modelError"
      :loading="modelLoading"
      :selection="runSelection"
      @refresh="$emit('refreshModels')"
      @select="$emit('selectRunConfig', $event)"
    />
    <div class="runner-action-buttons">
      <button class="secondary-button" type="button" :disabled="disabled || busy || caseCount === 0" :title="disabledReason" @click="$emit('runAll')">
        <Play :size="17" />
        {{ busy ? "运行中..." : "运行全部" }}
      </button>
      <button class="secondary-button" type="button" :disabled="disabled || busy || summary.failedRuns === 0" :title="disabledReason || (summary.failedRuns === 0 ? '当前没有失败的测试例可重试。' : '')" @click="$emit('retryFailed')">
        <RotateCcw :size="17" />
        重试失败
      </button>
      <button class="primary-button" type="button" :disabled="!canRunFormal" :title="formalDisabledReason" @click="$emit('runFormal')">
        <RotateCcw :size="17" />
        {{ busy ? "正式测评中..." : "运行正式测评" }}
      </button>
    </div>
  </div>
</template>
