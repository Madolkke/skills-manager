<script setup lang="ts">
import { Check, Search } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import type { CollectionDefinition, WorkflowCollectionChange } from "../../../types";

const props = defineProps<{ definitions: CollectionDefinition[]; changes: WorkflowCollectionChange[]; readonly: boolean }>();
const emit = defineEmits<{ select: [definition: CollectionDefinition] }>();
const root = ref<HTMLElement | null>(null);
const input = ref<HTMLInputElement | null>(null);
const query = ref("");
const open = ref(false);

const latest = computed(() => {
  const definitions = new Map<string, CollectionDefinition>();
  props.definitions.forEach((item) => {
    const current = definitions.get(item.id);
    if (!current || item.revision >= current.revision) definitions.set(item.id, item);
  });
  return [...definitions.values()].sort((left, right) => left.metadata.name.localeCompare(right.metadata.name, "zh-CN"));
});
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return latest.value.filter((item) => !needle || [item.metadata.name, item.key, item.spec.commandTemplate]
    .join(" ")
    .toLocaleLowerCase()
    .includes(needle));
});

onMounted(() => document.addEventListener("pointerdown", closeOutside));
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOutside));

function choose(definition: CollectionDefinition): void {
  emit("select", definition);
  query.value = "";
  open.value = false;
  void nextTick(() => input.value?.focus());
}

function pendingLabel(id: string): string {
  const change = props.changes.find((item) => item.definition.id === id);
  return change?.operation === "create" ? "待入库" : change?.operation === "fork" ? "副本" : change?.operation === "revise" ? "待修订" : "";
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
        placeholder="搜索名称、Key 或命令"
        aria-label="搜索共享采集"
        :disabled="props.readonly"
        @focus="open = true"
        @keydown.escape="open = false"
        @keydown.down.prevent="open = true"
      />
    </label>
    <Transition name="workflow-popover">
      <div v-if="open && !props.readonly" class="workflow-picker-menu">
        <button v-for="item in filtered" :key="`${item.id}-${item.revision}`" type="button" @click="choose(item)">
          <span><strong>{{ item.metadata.name || "未命名采集" }}</strong><code>{{ item.key }}</code></span>
          <small>{{ item.spec.commandTemplate || "未配置命令" }}</small>
          <i v-if="pendingLabel(item.id)">{{ pendingLabel(item.id) }}</i>
          <span v-else class="workflow-picker-revision">r{{ item.revision }}</span>
          <Check :size="14" />
        </button>
        <p v-if="filtered.length === 0">没有匹配的采集定义</p>
      </div>
    </Transition>
  </div>
</template>
