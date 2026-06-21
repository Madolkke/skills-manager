<script setup lang="ts">
import clsx from "clsx";
import { ChevronDown, Copy, FileText, ScrollText } from "lucide-vue-next";
import { computed, ref } from "vue";
import { compactText } from "../../../lib/format";
import type { EvalRunDetail } from "../../../types";
import CaseStepTimeline from "./CaseStepTimeline.vue";

type CaseResultItem = EvalRunDetail["case_results"][number];

const props = defineProps<{ item: CaseResultItem }>();
const emit = defineEmits<{ copy: [label: string, value: string] }>();

const passed = computed(() => props.item.result.passed);
const steps = computed(() => props.item.case_version.steps ?? []);
const output = computed(() => props.item.result_artifact?.content_text?.trim() ?? "");
const resultText = computed(() => (passed.value ? "通过" : "不通过"));
const scoreText = computed(() => String(props.item.result.score ?? (passed.value ? 1 : 0)));
const expanded = ref(false);

function copyOutput(): void {
  if (output.value) emit("copy", "运行结果", output.value);
}

function toggleExpanded(): void {
  expanded.value = !expanded.value;
}

function toggleWithKeyboard(event: KeyboardEvent): void {
  if (event.key !== "Enter" && event.key !== " ") return;
  if (event.target !== event.currentTarget) return;
  event.preventDefault();
  toggleExpanded();
}
</script>

<template>
  <article
    :class="clsx('history-case-result-card', passed ? 'passed' : 'failed', !expanded && 'collapsed')"
    role="button"
    tabindex="0"
    :aria-expanded="expanded"
    @click="toggleExpanded"
    @keydown="toggleWithKeyboard"
  >
    <header class="history-case-result-head">
      <div class="history-case-result-main">
        <div class="history-case-title-row">
          <h3>{{ item.case.title }}</h3>
          <span :class="clsx('case-result-chip', passed ? 'passed' : 'failed')">{{ resultText }}</span>
        </div>
        <div class="history-case-meta-row">
          <span><small>测试例版本</small><strong>v{{ item.case_version.version_number }}</strong></span>
          <span><small>判定结果</small><strong>{{ resultText }}</strong></span>
          <span><small>得分</small><strong>{{ scoreText }}</strong></span>
        </div>
      </div>
      <div class="history-case-result-actions">
        <ChevronDown :class="clsx('history-toggle-icon', expanded && 'expanded')" :size="18" aria-hidden="true" />
      </div>
    </header>

    <Transition name="history-collapse">
      <div v-if="expanded" class="history-collapse-box" @click.stop @keydown.stop>
        <div class="history-collapse-inner history-case-detail-stack">
          <section class="history-result-section history-case-steps">
            <CaseStepTimeline :steps="steps" @copy="emit('copy', '测试步骤', $event)" />
          </section>

          <section class="history-result-section">
            <header>
              <span><FileText :size="16" />运行结果</span>
              <button class="secondary-button compact" type="button" :disabled="!output" @click.stop="copyOutput" @keydown.stop>
                <Copy :size="15" />
                复制结果
              </button>
            </header>
            <div class="history-output-panel">
              <ScrollText v-if="!output" :size="18" />
              <pre v-if="output">{{ output }}</pre>
              <p v-else>{{ compactText(output, "没有可展示的文本结果。文件类或过程类判断模板可能只记录了判定结论。") }}</p>
            </div>
          </section>
        </div>
      </div>
    </Transition>
  </article>
</template>
