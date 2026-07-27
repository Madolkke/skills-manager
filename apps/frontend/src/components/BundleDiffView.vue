<script setup lang="ts">
import clsx from "clsx";
import { computed } from "vue";
import type { BundleDiffFile, BundleDiffLine, BundleDiffStatus } from "../types";

type DiffData = {
  summary: { added: number; changed: number; removed: number; unchanged: number; binary: number };
  files: BundleDiffFile[];
};

const props = withDefaults(defineProps<{
  diff?: DiffData | null;
  eyebrow?: string;
  title: string;
  stateMessage?: string;
}>(), { diff: null, eyebrow: "Skill 内容差异", stateMessage: undefined });

const visibleFiles = computed(() => {
  const files = props.diff?.files ?? [];
  const changed = files.filter((file) => file.status !== "unchanged");
  return changed.length > 0 ? changed : files;
});

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
</script>

<template>
  <section class="commit-diff-panel" aria-label="Skill 内容差异">
    <header class="commit-diff-head">
      <div>
        <span>{{ props.eyebrow }}</span>
        <h2>{{ props.title }}</h2>
      </div>
      <div class="commit-diff-tools">
        <slot name="tools" />
        <div v-if="props.diff" class="commit-diff-stats" aria-label="变更摘要">
          <span :class="clsx('commit-diff-stat', 'changed')"><strong>{{ props.diff.summary.changed }}</strong><small>变更</small></span>
          <span :class="clsx('commit-diff-stat', 'added')"><strong>{{ props.diff.summary.added }}</strong><small>新增</small></span>
          <span :class="clsx('commit-diff-stat', 'removed')"><strong>{{ props.diff.summary.removed }}</strong><small>移除</small></span>
        </div>
      </div>
    </header>

    <div v-if="props.stateMessage" class="quiet-panel">{{ props.stateMessage }}</div>
    <div v-else-if="props.diff && visibleFiles.length === 0" class="quiet-panel">文件内容无变化。</div>
    <div v-else-if="props.diff" class="commit-file-list">
      <article v-for="file in visibleFiles" :key="`${file.status}:${file.path}`" class="commit-file">
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
