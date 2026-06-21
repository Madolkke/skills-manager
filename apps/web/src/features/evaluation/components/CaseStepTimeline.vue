<script setup lang="ts">
import { Copy, FileText, ListChecks } from "lucide-vue-next";
import { computed } from "vue";
import { compactText } from "../../../lib/format";
import type { EvalCaseStep } from "../../../types";

const props = defineProps<{ steps: EvalCaseStep[] }>();
const emit = defineEmits<{ copy: [value: string] }>();

type AssertionParamRow = { name: string; value: string; multiline: boolean };

const stepCountLabel = computed(() => `${props.steps.length} 个步骤`);

function copyAllSteps(): void {
  emit("copy", JSON.stringify(props.steps, null, 2));
}

function copyStep(step: EvalCaseStep): void {
  emit("copy", JSON.stringify(step, null, 2));
}

function assertionParamRows(params: Record<string, unknown> = {}): AssertionParamRow[] {
  return Object.keys(params)
    .sort((left, right) => left.localeCompare(right))
    .map((name) => {
      const rawValue = params[name];
      const value = formatAssertionParamValue(rawValue);
      return {
        name,
        value,
        multiline: Array.isArray(rawValue) || isPlainObject(rawValue) || value.length > 72 || value.includes("\n"),
      };
    });
}

function paramSummary(params: Record<string, unknown> = {}): string {
  const count = Object.keys(params).length;
  return count > 0 ? `${count} 个参数` : "无需额外参数";
}

function formatAssertionParamValue(value: unknown): string {
  if (value === null || value === undefined) return "无内容";
  if (typeof value === "string") return compactText(value, "无内容");
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2) ?? "无内容";
  } catch {
    return String(value);
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
</script>

<template>
  <section class="case-block case-steps-section">
    <header class="case-steps-overview">
      <div>
        <span class="case-section-kicker"><ListChecks :size="15" />测试流程</span>
        <h2>测试步骤</h2>
        <p>{{ stepCountLabel }}，按顺序发送给 Agent；任一步不通过，整个测试例不通过。</p>
      </div>
      <button class="secondary-button case-copy-all" type="button" @click="copyAllSteps">
        <Copy :size="16" />
        复制全部步骤
      </button>
    </header>

    <div v-if="steps.length === 0" class="case-steps-empty">还没有配置测试步骤。</div>
    <div v-else class="case-step-timeline">
      <article v-for="(step, index) in steps" :key="step.id" class="case-step-card">
        <div class="case-step-rail">
          <span class="case-step-index">{{ index + 1 }}</span>
          <span v-if="index < steps.length - 1" class="case-step-line" />
        </div>
        <div class="case-step-body">
          <header class="case-step-card-head">
            <div>
              <strong>{{ compactText(step.title, `步骤 ${index + 1}`) }}</strong>
              <span class="case-template-chip">{{ step.assertion_template_id }}</span>
            </div>
            <div class="case-step-card-tools">
              <span class="case-param-count">{{ paramSummary(step.assertion_params) }}</span>
              <button class="icon-button mini" type="button" :aria-label="`复制步骤 ${index + 1}`" @click="copyStep(step)">
                <Copy :size="15" />
              </button>
            </div>
          </header>

          <div class="case-step-panels">
            <section class="case-step-panel case-step-input-panel">
              <header><FileText :size="15" /><span>输入给 Agent</span></header>
              <pre>{{ compactText(step.input, "无内容") }}</pre>
            </section>
            <section class="case-step-panel case-step-param-panel">
              <header><ListChecks :size="15" /><span>判断参数</span></header>
              <p v-if="assertionParamRows(step.assertion_params).length === 0" class="case-step-empty">无需额外参数</p>
              <div v-else class="case-step-param-grid">
                <div v-for="row in assertionParamRows(step.assertion_params)" :key="row.name" class="case-param-row">
                  <b>{{ row.name }}</b>
                  <pre v-if="row.multiline" class="case-param-value">{{ row.value }}</pre>
                  <span v-else class="case-param-value">{{ row.value }}</span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
