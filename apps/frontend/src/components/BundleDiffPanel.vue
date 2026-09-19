<script setup lang="ts">
import { ref, watch } from "vue";
import BundleDiffView from "./BundleDiffView.vue";
import RemoteVersionSelect from "./RemoteVersionSelect.vue";
import { api, ApiError } from "../lib/api";
import { versionName } from "../lib/format";
import type { BundleDiff, SkillVersion } from "../types";

const props = defineProps<{ current: SkillVersion; previous?: SkillVersion | null; versionCount: number }>();

const baseVersionId = ref(props.previous?.id ?? "");
const diff = ref<BundleDiff | null>(null);
const error = ref<string | null>(null);
const loading = ref(false);

const baseVersion = ref(props.previous ?? null);

watch(() => [props.current.id, props.previous?.id] as const, () => {
  baseVersionId.value = props.previous?.id ?? "";
  baseVersion.value = props.previous ?? null;
});

watch([() => baseVersion.value?.id, () => props.current.id], async (_, __, cleanup) => {
  let expired = false;
  cleanup(() => { expired = true; });
  diff.value = null;
  error.value = null;
  loading.value = false;
  if (!baseVersion.value) return;
  loading.value = true;
  try {
    const result = await api.getBundleDiff(baseVersion.value.id, props.current.id);
    if (!expired) diff.value = result;
  } catch (caught) {
    if (!expired) error.value = errorMessage(caught);
  } finally {
    if (!expired) loading.value = false;
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
    :state-message="loading ? '正在读取 Skill 内容差异...' : error ? `Skill 内容差异读取失败：${error}` : versionCount < 2 ? '这是第一个 Skill 版本，没有可比较的版本。' : undefined"
  >
    <template #tools>
      <label class="diff-version-select">
        <span>对比版本</span>
        <RemoteVersionSelect v-model="baseVersionId" :skill-id="current.skill_id" :exclude-id="current.id" @selected="baseVersion = $event" />
      </label>
    </template>
  </BundleDiffView>
</template>
