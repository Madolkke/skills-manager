<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BundleDiffView from "./BundleDiffView.vue";
import DropdownSelect from "./DropdownSelect.vue";
import { api, ApiError } from "../lib/api";
import { versionName } from "../lib/format";
import type { BundleDiff, SkillVersion } from "../types";

const props = defineProps<{ current: SkillVersion; previous?: SkillVersion | null; versions: SkillVersion[] }>();

const baseVersionId = ref(props.previous?.id ?? "");
const diff = ref<BundleDiff | null>(null);
const error = ref<string | null>(null);
const loading = ref(false);
const compareOptions = computed(() => props.versions.filter((version) => version.id !== props.current.id));
const compareSelectOptions = computed(() => compareOptions.value.map((version) => ({
  value: version.id,
  label: `${versionName(version)}${version.id === props.previous?.id ? "（前一个）" : ""}`,
})));
const baseVersion = computed(() => compareOptions.value.find((version) => version.id === baseVersionId.value) ?? null);

watch(() => [props.current.id, props.previous?.id] as const, () => {
  baseVersionId.value = props.previous?.id ?? "";
});

watch([baseVersion, () => props.current.id], async () => {
  diff.value = null;
  error.value = null;
  if (!baseVersion.value) return;
  loading.value = true;
  try {
    diff.value = await api.getBundleDiff(baseVersion.value.id, props.current.id);
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    loading.value = false;
  }
}, { immediate: true });

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
</script>

<template>
  <BundleDiffView
    :diff="diff"
    :title="baseVersion ? `${versionName(current)} 对比 ${versionName(baseVersion)}` : '初始版本'"
    :state-message="loading ? '正在读取 Skill 内容差异...' : error ? `Skill 内容差异读取失败：${error}` : compareOptions.length === 0 ? '这是第一个 Skill 版本，没有可比较的版本。' : undefined"
  >
    <template #tools>
      <label v-if="compareOptions.length > 0" class="diff-version-select">
        <span>对比版本</span>
        <DropdownSelect v-model="baseVersionId" :options="compareSelectOptions" aria-label="选择对比版本" compact />
      </label>
    </template>
  </BundleDiffView>
</template>
