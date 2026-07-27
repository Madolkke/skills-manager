<script setup lang="ts">
import { Files, GitCompareArrows } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import BundleBrowser from "../../../components/BundleBrowser.vue";
import BundleDiffView from "../../../components/BundleDiffView.vue";
import type { WorkflowSyncPreview, WorkflowSyncWarning } from "../../../types";

const props = defineProps<{ preview: WorkflowSyncPreview }>();
const tab = ref<"files" | "diff">("files");

const actionLabel = computed(() => {
  if (props.preview.action.mode === "reactivate") return "重新激活既有版本";
  if (props.preview.action.mode === "already_current") return "当前版本已匹配";
  return "创建新版本";
});

watch(() => props.preview.preview_digest, () => { tab.value = "files"; });

function warningMessage(warning: WorkflowSyncWarning): string {
  return typeof warning === "string" ? warning : warning.message;
}
</script>

<template>
  <section class="workflow-skill-preview" aria-label="同步预览">
    <header class="workflow-preview-summary">
      <div>
        <span>{{ actionLabel }}</span>
        <strong>Workflow revision {{ props.preview.workflow_revision }}</strong>
      </div>
      <dl>
        <div><dt>文件</dt><dd>{{ props.preview.files.length }}</dd></div>
        <div><dt>变更</dt><dd>{{ props.preview.diff.summary.added + props.preview.diff.summary.changed + props.preview.diff.summary.removed }}</dd></div>
      </dl>
    </header>

    <div v-if="props.preview.warnings.length" class="workflow-preview-warnings" role="status">
      <strong>{{ props.preview.warnings.length }} 个提醒</strong>
      <ul><li v-for="(warning, index) in props.preview.warnings" :key="index">{{ warningMessage(warning) }}</li></ul>
    </div>

    <div class="workflow-preview-tabs" role="tablist" aria-label="预览内容">
      <button type="button" role="tab" :aria-selected="tab === 'files'" :class="tab === 'files' && 'active'" @click="tab = 'files'"><Files :size="16" />文件</button>
      <button type="button" role="tab" :aria-selected="tab === 'diff'" :class="tab === 'diff' && 'active'" @click="tab = 'diff'"><GitCompareArrows :size="16" />差异</button>
    </div>

    <BundleBrowser v-if="tab === 'files'" :files="props.preview.files" root-label="skill/" />
    <BundleDiffView v-else :diff="props.preview.diff" eyebrow="与当前 Skill 版本对比" title="生成结果差异" />
  </section>
</template>
