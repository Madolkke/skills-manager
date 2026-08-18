<script setup lang="ts">
import { Check, Search } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import type {
  CollectionDefinition,
  CommandLibrarySearchResult,
  VersionedRef,
  WorkflowCollectionChange,
} from "../../../types";
import { collectionLibraryItems, type CollectionLibraryItem } from "../domain/collectionLibrary";
import { useCommandLibrarySearch } from "../useCommandLibrarySearch";

const props = defineProps<{
  definitions: CollectionDefinition[];
  currentDefinitionRefs: VersionedRef[];
  changes: WorkflowCollectionChange[];
  readonly: boolean;
}>();
const emit = defineEmits<{ select: [definition: CollectionDefinition]; "select-command": [result: CommandLibrarySearchResult] }>();
const root = ref<HTMLElement | null>(null);
const input = ref<HTMLInputElement | null>(null);
const query = ref("");
const open = ref(false);
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
const searchPlaceholder = computed(() => "搜索命令行");

onMounted(() => document.addEventListener("pointerdown", closeOutside));
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOutside));
function choose(item: CollectionLibraryItem): void {
  if (item.definition) emit("select", item.definition);
  else if (item.result) emit("select-command", item.result);
  query.value = "";
  open.value = false;
  void nextTick(() => input.value?.focus());
}

function pendingLabel(item: CollectionLibraryItem): string {
  if (!item.definition) return "";
  const operation = props.changes.find((change) => change.definition.id === item.definition?.id)?.operation;
  return operation === "create" ? "待入库" : operation === "fork" ? "副本" : operation === "revise" ? "待修订" : "";
}

function closeOutside(event: PointerEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false;
}
</script>

<template>
  <div ref="root" class="workflow-collection-picker">
    <label :class="['workflow-picker-input', open && 'active']">
      <Search :size="15" />
      <input
        ref="input"
        v-model="query"
        type="search"
        :placeholder="searchPlaceholder"
        aria-label="搜索采集库"
        :disabled="props.readonly"
        @focus="open = true"
        @keydown.escape="open = false"
        @keydown.down.prevent="open = true"
      />
    </label>
    <Transition name="workflow-popover">
      <div v-if="open && !props.readonly" class="workflow-picker-menu">
        <label class="workflow-command-toggle"><input v-model="includeUser" type="checkbox" />显示用户命令</label>
        <p v-if="commandSearch.error.value" class="workflow-command-error">{{ commandSearch.error.value }}</p>
        <button v-for="item in items" :key="item.id" type="button" @click="choose(item)">
          <span><strong>{{ item.name }}</strong><code>{{ item.source === "system" ? "系统" : item.source === "user" ? "用户" : item.definition?.key }}</code></span>
          <small>{{ item.summary }}<template v-if="item.result?.complete === false"> · 部分匹配</template><template v-if="item.result?.nextTokens?.length"> · {{ item.result.nextTokens.join(" / ") }}</template></small>
          <i v-if="pendingLabel(item)">{{ pendingLabel(item) }}</i>
          <span v-else-if="item.current" class="workflow-picker-revision">当前</span>
          <Check :size="14" />
        </button>
        <p v-if="commandSearch.loading.value">正在搜索命令…</p>
        <p v-else-if="items.length === 0">当前分类没有匹配的采集信息</p>
      </div>
    </Transition>
  </div>
</template>
