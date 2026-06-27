<script setup lang="ts">
import clsx from "clsx";
import { computed, ref, watch } from "vue";
import DropdownSelect from "./DropdownSelect.vue";
import { api, ApiError } from "../lib/api";
import { versionName } from "../lib/format";
import type { BundleDiff, BundleDiffFile, BundleDiffLine, BundleDiffStatus, SkillVersion } from "../types";

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
const changedFiles = computed(() => diff.value?.files.filter((file) => file.status !== "unchanged") ?? []);

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

function statusLabel(status: BundleDiffStatus): string {
  if (status === "added") return "新增";
  if (status === "changed") return "变更";
  if (status === "removed") return "移除";
  return "未变更";
}

function linePrefix(kind: BundleDiffLine["kind"]): string {
  if (kind === "added") return "+";
  if (kind === "removed") return "-";
  return " ";
}

function formatDiffSize(file: BundleDiffFile): string {
  const size = file.right_size_bytes ?? file.left_size_bytes ?? 0;
  if (!size) return "-";
  if (size < 1024) return `${size} B`;
  return `${Math.round(size / 102.4) / 10} KB`;
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
</script>

<template>
  <section class="commit-diff-panel" aria-label="Bundle 差异">
    <header class="commit-diff-head">
      <div>
        <span>Bundle 差异</span>
        <h2>{{ baseVersion ? `${versionName(current)} 对比 ${versionName(baseVersion)}` : "初始版本" }}</h2>
      </div>
      <div class="commit-diff-tools">
        <label v-if="compareOptions.length > 0" class="diff-version-select">
          <span>对比版本</span>
          <DropdownSelect v-model="baseVersionId" :options="compareSelectOptions" aria-label="选择对比版本" compact />
        </label>
        <div v-if="diff" class="commit-diff-stats" aria-label="变更摘要">
          <span :class="clsx('commit-diff-stat', 'changed')"><strong>{{ diff.summary.changed }}</strong><small>变更</small></span>
          <span :class="clsx('commit-diff-stat', 'added')"><strong>{{ diff.summary.added }}</strong><small>新增</small></span>
          <span :class="clsx('commit-diff-stat', 'removed')"><strong>{{ diff.summary.removed }}</strong><small>移除</small></span>
        </div>
      </div>
    </header>

    <div v-if="loading" class="quiet-panel">正在读取后端 Bundle 差异...</div>
    <div v-if="error" class="quiet-panel">Bundle 差异读取失败：{{ error }}</div>
    <div v-if="!loading && !error && compareOptions.length === 0" class="quiet-panel">这是第一个 Skill 版本，没有可比较的版本。</div>
    <div v-if="!loading && !error && diff" class="commit-file-list">
      <article v-for="file in (changedFiles.length > 0 ? changedFiles : diff.files)" :key="`${file.status}:${file.path}`" class="commit-file">
        <header>
          <span :class="clsx('file-status', file.status)">{{ statusLabel(file.status) }}</span>
          <strong>{{ file.path }}</strong>
          <small>{{ formatDiffSize(file) }}</small>
        </header>
        <div v-if="file.binary" class="quiet-panel">二进制文件变更，无法展示文本差异。</div>
        <div v-if="file.hunks?.length" class="commit-hunks">
          <pre v-for="(hunk, index) in file.hunks" :key="index">
<span v-for="(line, lineIndex) in hunk.lines" :key="`${line.old_line}:${line.new_line}:${lineIndex}`" :class="line.kind"><b>{{ linePrefix(line.kind) }}</b><code>{{ line.text || " " }}</code></span>
          </pre>
        </div>
      </article>
    </div>
  </section>
</template>
