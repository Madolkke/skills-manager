<script setup lang="ts">
import { Library, Plus, Search, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type {
  CollectionDefinition,
  CommandLibrarySearchResult,
  VersionedRef,
  WorkflowCollectionChange,
} from "../../../types";
import { collectionLibraryItems, type CollectionLibraryItem } from "../domain/collectionLibrary";
import { useCommandLibrarySearch } from "../useCommandLibrarySearch";
import WorkflowCollectionFields from "./WorkflowCollectionFields.vue";

const props = withDefaults(defineProps<{
  definitions: CollectionDefinition[];
  currentDefinitionRefs: VersionedRef[];
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
  "select-command": [result: CommandLibrarySearchResult];
}>();
const query = ref("");
const commandSearch = useCommandLibrarySearch(query);
const includeUser = commandSearch.includeUser;
const items = computed(() => collectionLibraryItems({
  type: "cli",
  definitions: props.definitions,
  currentDefinitionRefs: props.currentDefinitionRefs,
  commandResults: commandSearch.results.value,
  includeUser: includeUser.value,
  query: query.value,
}));
const selected = computed(() => {
  if (!props.selectedRef) return undefined;
  return props.definitions.find((item) => (
    item.id === props.selectedRef?.id
    && item.revision === props.selectedRef?.revision
    && item.spec.collectionType === "cli"
  ));
});
const selectedChange = computed(() => props.changes.find((item) => item.definition.id === selected.value?.id));
const removable = computed(() => Boolean(
  selected.value
  && !props.referencedDefinitionIds.includes(selected.value.id)
  && selectedChange.value
  && selectedChange.value.operation !== "revise",
));
const searchPlaceholder = computed(() => "搜索原始命令、名称或 Key");
const emptyLabel = computed(() => includeUser.value ? "没有匹配的系统或用户命令。" : "暂无匹配的系统命令。");

watch([() => props.selectedRef, () => props.definitions], () => {
  const definition = props.selectedRef
    ? props.definitions.find((item) => item.id === props.selectedRef?.id && item.revision === props.selectedRef?.revision)
    : undefined;
  if (definition?.spec.collectionType !== "cli") return;
}, { immediate: true });

function selectItem(item: CollectionLibraryItem): void {
  if (item.definition) emit("select", { id: item.definition.id, revision: item.definition.revision });
  else if (item.result) emit("select-command", item.result);
}

function addDefinition(): void {
  includeUser.value = true;
  emit("add");
}

function changeLabel(id: string): string {
  const operation = props.changes.find((item) => item.definition.id === id)?.operation;
  return operation === "create" ? "待入库" : operation === "fork" ? "副本" : operation === "revise" ? "待修订" : "";
}
</script>

<template>
  <section class="workflow-document workflow-library">
    <header class="workflow-document-head">
      <span><Library :size="18" /></span>
      <div><small>COLLECTION LIBRARY</small><h2>采集库</h2><p>按采集类型查找来源，并管理当前 Workflow 的精确定义。</p></div>
      <UiButton variant="secondary" :disabled="props.readonly" @click="addDefinition"><template #icon><Plus /></template>新建采集</UiButton>
    </header>
    <div class="workflow-library-layout">
      <aside class="workflow-library-list">
        <label class="workflow-library-search"><Search :size="15" /><input v-model="query" type="search" :placeholder="searchPlaceholder" /></label>
        <label class="workflow-command-toggle"><input v-model="includeUser" type="checkbox" />显示用户命令</label>
        <p v-if="commandSearch.error.value" class="workflow-command-error">{{ commandSearch.error.value }}</p>
        <button
          v-for="item in items"
          :key="item.id"
          :class="['workflow-library-item', item.source && 'workflow-command-item', item.definition?.id === selected?.id && item.definition?.revision === selected?.revision && 'active']"
          type="button"
          @click="selectItem(item)"
        >
          <span><strong>{{ item.name }}</strong><i v-if="item.source">{{ item.source === "system" ? "系统" : "用户" }}<template v-if="item.current"> · 当前</template></i><i v-else-if="item.current">当前</i></span>
          <code>{{ item.summary }}</code>
          <small v-if="item.result">{{ item.result.complete === false ? "部分匹配" : "完整匹配" }}<template v-if="item.result.nextTokens?.length"> · {{ item.result.nextTokens.join(" / ") }}</template></small>
          <small v-else-if="item.definition">{{ item.definition.key }} · r{{ item.definition.revision }}<template v-if="changeLabel(item.definition.id)"> · {{ changeLabel(item.definition.id) }}</template></small>
        </button>
        <p v-if="commandSearch.loading.value" class="workflow-empty">正在搜索命令…</p>
        <p v-else-if="items.length === 0" class="workflow-empty">{{ emptyLabel }}</p>
      </aside>
      <div v-if="selected" class="workflow-library-detail">
        <div class="workflow-library-detail-head">
          <div><strong>{{ selected.metadata.name || "未命名采集" }}</strong><span>revision {{ selected.revision }}</span><span v-if="selectedChange">{{ changeLabel(selected.id) }}</span><span v-if="selected.sourceSystemCommandId">系统来源</span><span v-if="selected.forkedFrom">来自副本</span></div>
          <UiIconButton v-if="removable" label="删除未保存采集" size="sm" variant="danger" @click="emit('remove', selected.id)"><Trash2 /></UiIconButton>
        </div>
        <WorkflowCollectionFields :definition="selected" :readonly="props.readonly || Boolean(selected.sourceSystemCommandId)" @change="emit('change', { id: selected.id, revision: selected.revision }, $event)" />
      </div>
      <div v-else class="workflow-empty">选择一项以查看或添加到当前 Workflow。</div>
    </div>
  </section>
</template>
