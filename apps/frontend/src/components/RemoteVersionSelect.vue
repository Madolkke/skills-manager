<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { usePagedQuery } from "../composables/usePagedQuery";
import { paginationApi } from "../lib/api/paginationApi";
import type { SkillVersion } from "../types";
import PaginationBar from "./PaginationBar.vue";

const props = defineProps<{ skillId: string; modelValue: string; excludeId?: string; disabled?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [id: string]; selected: [version: SkillVersion] }>();
const query = ref("");
const chosen = ref<SkillVersion | null>(null);
const selectionError = ref("");
const selectionRetry = ref(0);
const { page, pageSize, items, total, loading, error, reload } = usePagedQuery("version-picker",
  () => ({ query: query.value, skill: props.skillId }),
  (params, signal) => { const { skill: _skill, ...rest } = params; return paginationApi.versions(props.skillId, rest, signal); }, { route: false });
const options = computed(() => [...(chosen.value && !items.value.some(v => v.id === chosen.value?.id) ? [chosen.value] : []), ...items.value].filter(v => v.id !== props.excludeId));
watch([() => props.modelValue, selectionRetry], async ([id], _, cleanup) => {
  const controller = new AbortController(); cleanup(() => controller.abort());
  if (!id) { chosen.value = null; return; }
  const local = items.value.find(v => v.id === id);
  selectionError.value = "";
  try { const version = local ?? (await paginationApi.version(id, controller.signal, false)).version;
    if (!controller.signal.aborted) { chosen.value = version; emit("selected", version); }
  } catch (caught) { if (!controller.signal.aborted) selectionError.value = caught instanceof Error ? caught.message : "已选版本加载失败"; }
}, { immediate: true });
function choose(id: string) { emit("update:modelValue", id); const item = options.value.find(v => v.id === id); if (item) emit("selected", item); }
</script>

<template>
  <div class="remote-version-select">
    <input v-model="query" type="search" placeholder="搜索版本" aria-label="搜索版本" :disabled="disabled" />
    <select :value="modelValue" aria-label="选择版本" :disabled="disabled" @change="choose(($event.target as HTMLSelectElement).value)">
      <option value="">选择版本</option><option v-for="version in options" :key="version.id" :value="version.id">{{ version.version }} {{ version.display_name }}</option>
    </select>
    <span v-if="selectionError" role="alert">{{ selectionError }} <button type="button" class="secondary-button" @click="selectionRetry++">重试已选版本</button></span>
    <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" :loading="loading" :error="error" @retry="reload" />
  </div>
</template>
<style scoped>.remote-version-select { min-width: 0; display: grid; gap: 8px; } select, input { width: 100%; min-width: 0; }</style>
