<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import VersionSelector from "../../../components/VersionSelector.vue";
import { nextPatchVersion, validSemver } from "../../../lib/semver";
import type { SkillDetail, WorkflowValidationIssue } from "../../../types";

const props = defineProps<{
  skill: SkillDetail;
  revision: number;
  issues: WorkflowValidationIssue[];
  busy: boolean;
  error?: string | null;
}>();
const emit = defineEmits<{
  close: [];
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
  <Modal title="同步到 Skill" description="本次同步将生成完整的新 bundle，并设为当前 Skill 版本。" @close="emit('close')">
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
        <button class="secondary-button" type="button" :disabled="props.busy" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
          {{ props.busy ? "同步中..." : "确认同步" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
