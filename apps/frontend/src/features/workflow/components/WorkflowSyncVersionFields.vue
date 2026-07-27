<script setup lang="ts">
import VersionSelector from "../../../components/VersionSelector.vue";
import type { SkillVersion, WorkflowSyncPreviewAction } from "../../../types";

const props = defineProps<{
  action: WorkflowSyncPreviewAction;
  versions: SkillVersion[];
  version: string;
  displayName: string;
  changeSummary: string;
}>();
const emit = defineEmits<{
  "update:version": [value: string];
  "update:displayName": [value: string];
  "update:changeSummary": [value: string];
}>();

const update = (event: Event): string => (event.target as HTMLInputElement | HTMLTextAreaElement).value;
</script>

<template>
  <section class="workflow-sync-version-fields" aria-labelledby="workflow-sync-version-heading">
    <div class="workflow-sync-section-heading">
      <div>
        <span>Skill Version</span>
        <strong id="workflow-sync-version-heading">{{ props.action.mode === "create" ? "版本信息" : "既有版本" }}</strong>
      </div>
    </div>

    <VersionSelector v-if="props.action.mode === 'create'" :model-value="props.version" :versions="props.versions" @update:model-value="emit('update:version', $event)" />
    <label v-else class="field-label compact">
      <span>版本号</span>
      <input :value="props.version" disabled />
    </label>
    <label class="field-label compact">
      <span>版本名称</span>
      <input :value="props.displayName" maxlength="80" :disabled="props.action.mode !== 'create'" @input="emit('update:displayName', update($event))" />
    </label>
    <label class="field-label compact">
      <span>变更说明</span>
      <textarea :value="props.changeSummary" maxlength="1024" rows="3" :disabled="props.action.mode !== 'create'" @input="emit('update:changeSummary', update($event))" />
    </label>
  </section>
</template>
