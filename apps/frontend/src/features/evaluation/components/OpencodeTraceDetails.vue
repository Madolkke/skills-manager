<script setup lang="ts">
import { BrainCircuit, Wrench } from "lucide-vue-next";
import type { OpencodeTrace, OpencodeToolCall } from "../lib/evalRunner";

defineProps<{ trace?: OpencodeTrace }>();

function hasTrace(trace?: OpencodeTrace): boolean {
  return Boolean(trace?.reasoning_text?.trim() || trace?.tool_calls?.length);
}

function formatInput(value: unknown): string {
  if (value === null || value === undefined) return "{}";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function toolLabel(call: OpencodeToolCall): string {
  return [call.tool || "未知工具", call.status || "未知状态"].join(" · ");
}
</script>

<template>
  <details v-if="hasTrace(trace)" class="opencode-trace-details">
    <summary>Opencode 过程</summary>
    <section v-if="trace?.reasoning_text?.trim()" class="opencode-trace-block">
      <header><BrainCircuit :size="15" /><span>reasoning</span></header>
      <pre>{{ trace.reasoning_text }}</pre>
    </section>
    <section v-if="trace?.tool_calls?.length" class="opencode-trace-block">
      <header><Wrench :size="15" /><span>工具调用</span></header>
      <div class="opencode-tool-list">
        <article v-for="call in trace.tool_calls" :key="call.call_id || `${call.tool}-${call.status}`" class="opencode-tool-call">
          <strong>{{ toolLabel(call) }}</strong>
          <pre>{{ formatInput(call.input) }}</pre>
          <small v-if="call.output_preview">{{ call.output_preview }}</small>
        </article>
      </div>
    </section>
  </details>
</template>
