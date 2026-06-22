<script setup lang="ts">
import clsx from "clsx";
import { ArrowDown, ArrowUp, CheckCircle2, Plus, Trash2 } from "lucide-vue-next";
import type { EvalAssertionTemplate, EvalCaseStep } from "../../../types";
import type { StepValidation } from "../lib/evalCaseForm";

const props = defineProps<{
  steps: EvalCaseStep[];
  selectedIndex: number;
  templates: EvalAssertionTemplate[];
  validations: StepValidation[];
  showValidation: boolean;
}>();
const emit = defineEmits<{ select: [index: number]; add: []; remove: [index: number]; move: [index: number, direction: -1 | 1] }>();

function assertionSummary(step: EvalCaseStep): string {
  if (step.assertions.length === 0) return "缺少判断条件";
  const first = step.assertions[0];
  const firstName = props.templates.find((template) => template.id === first.assertion_template_id)?.name ?? first.assertion_template_id;
  return step.assertions.length === 1 ? firstName : `${step.assertions.length} 个判断条件 · ${firstName}`;
}
</script>

<template>
  <aside class="scenario-step-nav">
    <header>
      <div>
        <strong>测试步骤</strong>
        <span>{{ steps.length }} 步，任一步失败则整体失败</span>
      </div>
      <button class="icon-button mini" type="button" aria-label="添加步骤" @click="emit('add')"><Plus :size="17" /></button>
    </header>
    <div class="scenario-step-list">
      <article
        v-for="(step, index) in steps"
        :key="`${step.id || 'new'}-${index}`"
        :class="clsx('scenario-step-item', selectedIndex === index && 'active', showValidation && !validations[index]?.complete && 'invalid')"
      >
        <button type="button" class="scenario-step-main" @click="emit('select', index)">
          <span class="scenario-step-index">{{ index + 1 }}</span>
          <span class="scenario-step-copy">
            <strong>{{ step.title || `步骤 ${index + 1}` }}</strong>
            <small>{{ assertionSummary(step) }}</small>
            <em v-if="showValidation && !validations[index]?.complete">{{ validations[index]?.message }}</em>
          </span>
          <CheckCircle2 v-if="validations[index]?.complete" :size="16" />
        </button>
        <div class="scenario-step-tools">
          <button class="icon-button mini" type="button" :disabled="index === 0" aria-label="上移步骤" @click="emit('move', index, -1)"><ArrowUp :size="15" /></button>
          <button class="icon-button mini" type="button" :disabled="index === steps.length - 1" aria-label="下移步骤" @click="emit('move', index, 1)"><ArrowDown :size="15" /></button>
          <button class="icon-button mini" type="button" :disabled="steps.length === 1" aria-label="删除步骤" @click="emit('remove', index)"><Trash2 :size="15" /></button>
        </div>
      </article>
    </div>
    <button class="secondary-button full-width" type="button" @click="emit('add')"><Plus :size="16" />添加步骤</button>
  </aside>
</template>
