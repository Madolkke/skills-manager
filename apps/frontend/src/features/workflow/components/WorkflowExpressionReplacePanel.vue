<script setup lang="ts">
import { computed, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowBundle } from "../../../types";
import { collectWorkflowExpressionReplacements, replacementStats, workflowExpressionReplaceFields, type WorkflowExpressionReplaceField } from "../workflowExpressionReplace";

const props = defineProps<{ bundle: WorkflowBundle; readonly: boolean }>();
const emit = defineEmits<{ replace: [payload: { search: string; replacement: string; fields: WorkflowExpressionReplaceField[] }] }>();
const search = ref("");
const replacement = ref("");
const selectedFields = ref<WorkflowExpressionReplaceField[]>(workflowExpressionReplaceFields.map((item) => item.id));
const lastApplied = ref<{ expressions: number; occurrences: number } | null>(null);

const matches = computed(() => collectWorkflowExpressionReplacements(props.bundle, search.value, replacement.value, selectedFields.value));
const stats = computed(() => replacementStats(matches.value));
const canReplace = computed(() => !props.readonly && Boolean(search.value) && selectedFields.value.length > 0 && stats.value.expressions > 0);

watch([search, replacement, selectedFields], () => { lastApplied.value = null; }, { deep: true });

function replaceAll(): void {
  if (!canReplace.value) return;
  lastApplied.value = stats.value;
  emit("replace", { search: search.value, replacement: replacement.value, fields: [...selectedFields.value] });
}
</script>

<template>
  <div class="workflow-expression-replace-panel">
    <section class="workflow-replace-form">
      <div class="workflow-replace-intro"><strong>全局表达式内容替换</strong><p>按纯文本查找并替换当前 Workflow 中选定字段的全部匹配内容。</p></div>
      <label class="field-label"><span>搜索内容</span><input v-model="search" aria-label="搜索内容" placeholder="例如：outputs.status" /></label>
      <label class="field-label"><span>替换为</span><input v-model="replacement" aria-label="替换为" placeholder="可留空以删除文本" /></label>
      <fieldset class="workflow-replace-fields"><legend>搜索范围</legend><label v-for="field in workflowExpressionReplaceFields" :key="field.id"><input v-model="selectedFields" type="checkbox" :value="field.id" :aria-label="field.label" /><span>{{ field.label }}</span></label></fieldset>
    </section>

    <section class="workflow-replace-summary" aria-live="polite">
      <strong>{{ stats.expressions }} 个表达式</strong><span>{{ stats.occurrences }} 处命中</span>
      <p v-if="lastApplied">已替换 {{ lastApplied.expressions }} 个表达式，共 {{ lastApplied.occurrences }} 处。</p>
      <p v-else-if="!search">输入搜索内容后显示命中预览。</p>
      <p v-else-if="!matches.length">没有匹配的表达式。</p>
    </section>

    <div v-if="matches.length" class="workflow-replace-matches" aria-label="替换预览">
      <article v-for="match in matches" :key="`${match.nodeId}:${match.field}:${match.transitionId ?? ''}`" class="workflow-replace-match">
        <header><strong>{{ match.nodeName || "未命名节点" }}</strong><span>{{ match.fieldLabel }} · {{ match.count }} 处</span></header>
        <div class="workflow-replace-value"><small>原文</small><pre>{{ match.original }}</pre></div>
        <div class="workflow-replace-value"><small>替换后</small><pre>{{ match.replaced }}</pre></div>
      </article>
    </div>

    <div class="workflow-replace-actions"><UiButton variant="primary" :disabled="!canReplace" :disabled-reason="props.readonly ? '只读模式无法替换 Workflow' : !search ? '请输入搜索内容' : !selectedFields.length ? '至少选择一个搜索范围' : '没有匹配的表达式'" @click="replaceAll">替换全部命中</UiButton></div>
  </div>
</template>
