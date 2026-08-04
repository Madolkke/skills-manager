<script setup lang="ts">
import { CirclePlus, Trash2 } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionDefinition, LogCollectionSpec, WorkflowLogSchemaCatalog } from "../../../types";
import { api } from "../../../lib/api";
import { cloneWorkflow, createWorkflowId } from "../domain/utils";
import { fallbackWorkflowLogSchema } from "../domain/logSchema";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean }>();
const emit = defineEmits<{ change: [spec: LogCollectionSpec] }>();
const catalog = ref<WorkflowLogSchemaCatalog>(fallbackWorkflowLogSchema);

onMounted(() => {
  void api.getWorkflowLogSchema().then((value) => { catalog.value = value; }).catch(() => undefined);
});

function currentSpec(): LogCollectionSpec {
  return props.definition.spec.collectionType === "log"
    ? props.definition.spec
    : { collectionType: "log", sqlDialect: "duckdb", queries: [], outputSamples: [] };
}

function update(recipe: (spec: LogCollectionSpec) => void): void {
  const spec = cloneWorkflow(currentSpec());
  recipe(spec);
  emit("change", spec);
}

function addQuery(): void {
  update((spec) => spec.queries.push({ id: createWorkflowId("log-query"), name: `聚合 ${spec.queries.length + 1}`, sql: "", outputIds: [] }));
}

function addSample(): void {
  update((spec) => spec.outputSamples.push({ id: createWorkflowId("log-sample"), name: `日志示例 ${spec.outputSamples.length + 1}`, text: "" }));
}

function updateOutputIds(queryId: string, event: Event): void {
  const selected = [...(event.target as HTMLSelectElement).selectedOptions].map((item) => item.value);
  update((spec) => {
    const query = spec.queries.find((item) => item.id === queryId);
    if (query) query.outputIds = selected;
  });
}
</script>

<template>
  <section class="workflow-field-section workflow-log-spec">
    <div class="workflow-subhead"><div><h3>日志聚合 SQL</h3><p>DuckDB SQL；运行侧将全量日志注册为 <code>logs</code>，参数注册为单行 <code>params</code>。</p></div><span class="workflow-log-contract-badge">只读契约</span></div>
    <div class="workflow-log-columns" aria-label="可用日志列">
      <strong>可用列</strong>
      <span v-for="column in catalog.columns" :key="column.name"><code>{{ column.name }}</code><small>{{ column.duckdb_type }} · {{ column.title }}</small></span>
    </div>
    <article v-for="query in (props.definition.spec.collectionType === 'log' ? props.definition.spec.queries : [])" :key="query.id" class="workflow-log-query">
      <header><label class="field-label"><span>查询名称</span><input :value="query.name" :disabled="props.readonly" @input="update((spec) => { const target = spec.queries.find((item) => item.id === query.id); if (target) target.name = ($event.target as HTMLInputElement).value; })" /></label><UiIconButton label="删除聚合查询" size="sm" variant="danger" :disabled="props.readonly" @click="update((spec) => { spec.queries = spec.queries.filter((item) => item.id !== query.id); })"><Trash2 /></UiIconButton></header>
      <label class="field-label"><span>输出字段</span><select multiple :value="query.outputIds" :disabled="props.readonly" @change="updateOutputIds(query.id, $event)"><option v-for="output in props.definition.outputs" :key="output.id" :value="output.id">{{ output.key || output.schema.title || output.id }}</option></select><small>每个输出只能归属一条查询；SQL alias 必须等于变量名。</small></label>
      <label class="field-label"><span>SQL</span><textarea class="workflow-log-sql-input" rows="8" spellcheck="false" placeholder="SELECT count(*) AS error_count FROM logs" :value="query.sql" :disabled="props.readonly" @input="update((spec) => { const target = spec.queries.find((item) => item.id === query.id); if (target) target.sql = ($event.target as HTMLTextAreaElement).value; })" /></label>
    </article>
    <div v-if="props.definition.spec.collectionType === 'log' && props.definition.spec.queries.length === 0" class="workflow-inline-empty">尚未添加聚合查询</div>
    <UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addQuery"><template #icon><CirclePlus /></template>添加聚合查询</UiButton>
  </section>

  <section class="workflow-field-section workflow-log-samples">
    <div class="workflow-subhead"><div><h3>日志样例</h3><p>仅保存原始文本用于作者预览，不进行解析或校验。</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addSample"><template #icon><CirclePlus /></template>添加</UiButton></div>
    <template v-if="props.definition.spec.collectionType === 'log'">
      <article v-for="sample in props.definition.spec.outputSamples" :key="sample.id" class="workflow-sample">
        <div><input :value="sample.name" aria-label="日志样例名称" :disabled="props.readonly" @input="update((spec) => { const target = spec.outputSamples.find((item) => item.id === sample.id); if (target) target.name = ($event.target as HTMLInputElement).value; })" /><UiIconButton label="删除日志样例" size="sm" variant="danger" :disabled="props.readonly" @click="update((spec) => { spec.outputSamples = spec.outputSamples.filter((item) => item.id !== sample.id); })"><Trash2 /></UiIconButton></div>
        <textarea class="workflow-sample-output" rows="6" spellcheck="false" :value="sample.text" :disabled="props.readonly" @input="update((spec) => { const target = spec.outputSamples.find((item) => item.id === sample.id); if (target) target.text = ($event.target as HTMLTextAreaElement).value; })" />
      </article>
    </template>
    <p v-if="props.definition.spec.collectionType !== 'log' || props.definition.spec.outputSamples.length === 0" class="workflow-inline-empty">尚未添加日志样例</p>
  </section>
</template>
