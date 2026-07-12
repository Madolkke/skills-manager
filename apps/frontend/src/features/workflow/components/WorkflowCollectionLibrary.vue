<script setup lang="ts">
import { Library, Plus, Search, Trash2 } from "lucide-vue-next";
import { computed, ref } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionDefinition, VersionedRef, WorkflowCollectionChange } from "../../../types";
import WorkflowCollectionFields from "./WorkflowCollectionFields.vue";

const props = withDefaults(defineProps<{
  definitions: CollectionDefinition[];
  selectedRef?: VersionedRef;
  changes: WorkflowCollectionChange[];
  referencedDefinitionIds?: string[];
  readonly: boolean;
}>(), { selectedRef: undefined, referencedDefinitionIds: () => [] });
const emit = defineEmits<{
  select: [reference: VersionedRef];
  add: [];
  change: [reference: VersionedRef, definition: CollectionDefinition];
  remove: [id: string];
}>();
const query = ref("");
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return props.definitions.filter((item) => !needle || [item.metadata.name, item.key, item.metadata.description, item.spec.commandTemplate]
    .join(" ")
    .toLocaleLowerCase()
    .includes(needle));
});
const selected = computed(() => props.selectedRef
  ? props.definitions.find((item) => item.id === props.selectedRef?.id && item.revision === props.selectedRef?.revision)
  : filtered.value[0]);
const selectedChange = computed(() => props.changes.find((item) => item.definition.id === selected.value?.id));
const removable = computed(() => Boolean(
  selected.value
  && !props.referencedDefinitionIds.includes(selected.value.id)
  && selectedChange.value
  && selectedChange.value.operation !== "revise",
));

function changeLabel(id: string): string {
  const operation = props.changes.find((item) => item.definition.id === id)?.operation;
  return operation === "create" ? "待入库" : operation === "fork" ? "副本" : operation === "revise" ? "待修订" : "";
}
</script>

<template>
  <section class="workflow-document workflow-library">
    <header class="workflow-document-head">
      <span><Library :size="18" /></span>
      <div><small>COLLECTION CATALOG</small><h2>共享采集库</h2><p>管理当前 Workflow 可复用的采集定义及精确 revision。</p></div>
      <UiButton variant="secondary" :disabled="props.readonly" @click="emit('add')"><template #icon><Plus /></template>新建采集</UiButton>
    </header>
    <div class="workflow-library-layout">
      <aside class="workflow-library-list">
        <label class="workflow-library-search"><Search :size="15" /><input v-model="query" type="search" placeholder="搜索名称、Key 或命令" /></label>
        <button v-for="item in filtered" :key="`${item.id}-${item.revision}`" :class="['workflow-library-item', selected?.id === item.id && selected?.revision === item.revision && 'active']" type="button" @click="emit('select', { id: item.id, revision: item.revision })">
          <span><strong>{{ item.metadata.name || "未命名采集" }}</strong><i v-if="changeLabel(item.id)">{{ changeLabel(item.id) }}</i></span>
          <code>{{ item.spec.commandTemplate || "未配置命令" }}</code>
          <small>{{ item.key }} · {{ item.metadata.device || "未指定设备" }} · r{{ item.revision }}</small>
        </button>
        <p v-if="filtered.length === 0" class="workflow-empty">没有匹配的采集定义。</p>
      </aside>
      <div v-if="selected" class="workflow-library-detail">
        <div class="workflow-library-detail-head">
          <div><strong>{{ selected.metadata.name || "未命名采集" }}</strong><span>revision {{ selected.revision }}</span><span v-if="selectedChange">{{ changeLabel(selected.id) }}</span><span v-if="selected.forkedFrom">来自副本</span></div>
          <UiIconButton v-if="removable" label="删除未保存采集" size="sm" variant="danger" @click="emit('remove', selected.id)"><Trash2 /></UiIconButton>
        </div>
        <WorkflowCollectionFields :definition="selected" :readonly="props.readonly" @change="emit('change', { id: selected.id, revision: selected.revision }, $event)" />
      </div>
      <div v-else class="workflow-empty">选择或新建一个采集定义。</div>
    </div>
  </section>
</template>
