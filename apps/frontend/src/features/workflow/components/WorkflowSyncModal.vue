<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import VersionSelector from "../../../components/VersionSelector.vue";
import { nextPatchVersion, validSemver } from "../../../lib/semver";
import type { SkillDetail, WorkflowValidationIssue } from "../../../types";

const props = withDefaults(defineProps<{
  skill: SkillDetail;
  open?: boolean;
  revision: number;
  issues: WorkflowValidationIssue[];
  busy: boolean;
  error?: string | null;
}>(), { open: true, error: undefined });
const emit = defineEmits<{
  close: [];
  closed: [];
  submit: [payload: { version: string; display_name?: string; change_summary: string }];
}>();

const version = ref(nextPatchVersion(props.skill.versions));
const displayName = ref("");
const changeSummary = ref(`从 Workflow revision ${props.revision} 同步。`);
const warnings = computed(() => props.issues.filter((item) => item.severity === "warning"));
const canSubmit = computed(() => !props.busy && validSemver(version.value) && Boolean(changeSummary.value.trim()));

watch(() => props.revision, (revision) => {
  changeSummary.value = `从 Workflow revision ${revision} 同步。`;
});
watch(() => props.open, (open) => {
  if (!open) return;
  version.value = nextPatchVersion(props.skill.versions);
  displayName.value = "";
  changeSummary.value = `从 Workflow revision ${props.revision} 同步。`;
});

function submit(): void {
  if (!canSubmit.value) return;
  const cleanName = displayName.value.trim();
  emit("submit", {
    version: version.value.trim(),
    display_name: cleanName || undefined,
    change_summary: changeSummary.value.trim(),
  });
}
</script>

<template>
  <Modal title="同步到 Skill" description="本次同步将生成完整的新 bundle，并设为当前 Skill 版本。" :open="props.open" motion="workflow" @close="emit('close')" @after-leave="emit('closed')">
    <div class="form-stack workflow-sync-form">
      <div v-if="props.error" class="form-error">{{ props.error }}</div>
      <div class="workflow-replace-warning">
        当前手工编辑内容不会合并到新版本；历史版本仍保留在版本列表中。
      </div>
      <div v-if="warnings.length" class="hint-strip">当前有 {{ warnings.length }} 个提醒，不阻止同步。</div>
      <VersionSelector v-model="version" :versions="props.skill.versions" />
      <label class="field-label">
        <span>版本名称</span>
        <input v-model="displayName" maxlength="80" :placeholder="`${props.skill.skill.slug} workflow`" />
      </label>
      <label class="field-label">
        <span>变更说明</span>
        <textarea v-model="changeSummary" maxlength="1024" rows="4" />
      </label>
      <div class="modal-actions">
        <UiButton variant="secondary" size="lg" :disabled="props.busy" @click="emit('close')">取消</UiButton>
        <UiButton variant="primary" size="lg" :state="props.busy ? 'loading' : 'idle'" :disabled="!canSubmit && !props.busy" loading-label="同步中" @click="submit">确认同步</UiButton>
      </div>
    </div>
  </Modal>
</template>
