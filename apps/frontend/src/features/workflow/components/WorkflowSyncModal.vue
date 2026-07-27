<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import { api, ApiError } from "../../../lib/api";
import { nextPatchVersion, validSemver } from "../../../lib/semver";
import type { SkillDetail, WorkflowSkillGenerator, WorkflowSyncPayload, WorkflowSyncPreview } from "../../../types";
import WorkflowGeneratorSelector from "./WorkflowGeneratorSelector.vue";
import WorkflowSkillPreview from "./WorkflowSkillPreview.vue";
import WorkflowSyncConfirmation from "./WorkflowSyncConfirmation.vue";
import WorkflowSyncVersionFields from "./WorkflowSyncVersionFields.vue";

const props = withDefaults(defineProps<{
  skill: SkillDetail;
  open?: boolean;
  revision: number;
  recoveryKey?: number;
  busy: boolean;
  error?: string | null;
}>(), { open: true, recoveryKey: 0, error: undefined });
const emit = defineEmits<{
  close: [];
  closed: [];
  previewed: [];
  submit: [payload: WorkflowSyncPayload];
}>();

const generators = ref<WorkflowSkillGenerator[]>([]);
const selectedGeneratorId = ref("");
const preview = ref<WorkflowSyncPreview | null>(null);
const catalogBusy = ref(false);
const previewBusy = ref(false);
const previewError = ref("");
const confirmed = ref(false);
const version = ref("");
const displayName = ref("");
const changeSummary = ref("");
let requestCycle = 0;

const formValid = computed(() => {
  if (!preview.value) return false;
  if (preview.value.action.mode !== "create") return Boolean(version.value);
  return validSemver(version.value) && Boolean(changeSummary.value.trim());
});
const canSubmit = computed(() => Boolean(preview.value && confirmed.value && formValid.value && !props.busy && !previewBusy.value));

watch(() => props.open, (open) => {
  if (open) void initialize(false);
  else invalidatePreview();
}, { immediate: true });
watch([() => props.revision, () => props.recoveryKey], () => {
  if (props.open) void initialize(true);
});

/**
 * Reloads the server registry, selects its declared default, and generates a preview.
 */
async function initialize(preserveSelection: boolean): Promise<void> {
  const cycle = ++requestCycle;
  invalidatePreview(false);
  catalogBusy.value = true;
  previewError.value = "";
  try {
    const catalog = await api.listWorkflowSkillGenerators();
    if (cycle !== requestCycle) return;
    generators.value = catalog.generators;
    const preserved = preserveSelection && catalog.generators.some((item) => item.id === selectedGeneratorId.value);
    selectedGeneratorId.value = preserved
      ? selectedGeneratorId.value
      : catalog.default_generator_id || catalog.generators.find((item) => item.default)?.id || catalog.generators[0]?.id || "";
    if (!selectedGeneratorId.value) {
      previewError.value = "服务端没有可用的 Workflow Generator。";
      return;
    }
    await generatePreview(cycle);
  } catch (caught) {
    if (cycle === requestCycle) previewError.value = errorMessage(caught, "Generator 列表加载失败。");
  } finally {
    if (cycle === requestCycle) catalogBusy.value = false;
  }
}

/**
 * Discards the prior confirmation before requesting a deterministic server preview.
 */
async function selectGenerator(generatorId: string): Promise<void> {
  if (generatorId === selectedGeneratorId.value) return;
  selectedGeneratorId.value = generatorId;
  const cycle = ++requestCycle;
  invalidatePreview(false);
  await generatePreview(cycle);
}

async function refreshPreview(): Promise<void> {
  const cycle = ++requestCycle;
  invalidatePreview(false);
  await generatePreview(cycle);
}

async function generatePreview(cycle: number): Promise<void> {
  previewBusy.value = true;
  previewError.value = "";
  try {
    const result = await api.previewWorkflowSync(props.skill.skill.id, {
      expected_workflow_revision: props.revision,
      generator_id: selectedGeneratorId.value,
      generator_options: {},
    });
    if (cycle !== requestCycle) return;
    preview.value = result;
    resetVersionFields(result);
    emit("previewed");
  } catch (caught) {
    if (cycle === requestCycle) previewError.value = errorMessage(caught, "同步预览生成失败。");
  } finally {
    if (cycle === requestCycle) previewBusy.value = false;
  }
}

function invalidatePreview(cancelRequest = true): void {
  if (cancelRequest) requestCycle += 1;
  preview.value = null;
  confirmed.value = false;
  previewError.value = "";
}

function resetVersionFields(result: WorkflowSyncPreview): void {
  const existing = result.action.mode !== "create";
  version.value = existing ? result.action.version || nextPatchVersion(props.skill.versions) : result.action.next_version || nextPatchVersion(props.skill.versions);
  displayName.value = existing ? result.action.display_name ?? "" : "";
  changeSummary.value = existing
    ? `重新激活 Workflow revision ${result.workflow_revision} 的既有版本。`
    : `从 Workflow revision ${result.workflow_revision} 同步。`;
  confirmed.value = false;
}

function updateField(field: "version" | "displayName" | "changeSummary", value: string): void {
  if (field === "version") version.value = value;
  else if (field === "displayName") displayName.value = value;
  else changeSummary.value = value;
  confirmed.value = false;
}

function submit(): void {
  if (!canSubmit.value || !preview.value) return;
  const cleanName = displayName.value.trim();
  emit("submit", {
    version: version.value.trim(),
    display_name: cleanName || undefined,
    change_summary: changeSummary.value.trim(),
    expected_workflow_revision: preview.value.workflow_revision,
    generator_id: preview.value.generator.id,
    generator_version: preview.value.generator.version,
    generator_options: preview.value.generator_options,
    preview_digest: preview.value.preview_digest,
  });
}

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}
</script>

<template>
  <Modal
    title="同步到 Skill"
    :description="`Workflow revision ${props.revision}`"
    size="workspace"
    :open="props.open"
    motion="workflow"
    @close="emit('close')"
    @after-leave="emit('closed')"
  >
    <div class="workflow-sync-shell">
      <div v-if="props.error" class="form-error">{{ props.error }}</div>
      <div v-if="previewError" class="form-error">{{ previewError }}</div>

      <div class="workflow-sync-generator-row">
        <WorkflowGeneratorSelector
          :generators="generators"
          :model-value="selectedGeneratorId"
          :disabled="catalogBusy || previewBusy || props.busy"
          @update:model-value="selectGenerator"
        />
        <UiButton variant="secondary" :disabled="!selectedGeneratorId || catalogBusy || props.busy" :state="previewBusy ? 'loading' : 'idle'" loading-label="生成中" @click="refreshPreview">
          <template #icon><RefreshCw /></template>
          重新预览
        </UiButton>
      </div>

      <div class="workflow-sync-layout">
        <div class="workflow-sync-preview-region">
          <div v-if="catalogBusy || previewBusy" class="quiet-panel">正在生成 Skill Bundle 预览...</div>
          <WorkflowSkillPreview v-else-if="preview" :preview="preview" />
          <div v-else-if="!previewError" class="quiet-panel">等待同步预览。</div>
        </div>

        <aside class="workflow-sync-sidebar">
          <WorkflowSyncVersionFields
            v-if="preview"
            :action="preview.action"
            :versions="props.skill.versions"
            :version="version"
            :display-name="displayName"
            :change-summary="changeSummary"
            @update:version="updateField('version', $event)"
            @update:display-name="updateField('displayName', $event)"
            @update:change-summary="updateField('changeSummary', $event)"
          />
          <WorkflowSyncConfirmation v-if="preview" v-model="confirmed" :revision="preview.workflow_revision" :disabled="props.busy" />
          <div class="modal-actions">
            <UiButton variant="secondary" size="lg" :disabled="props.busy" @click="emit('close')">取消</UiButton>
            <UiButton variant="primary" size="lg" :state="props.busy ? 'loading' : 'idle'" :disabled="!canSubmit && !props.busy" loading-label="同步中" @click="submit">确认同步</UiButton>
          </div>
        </aside>
      </div>
    </div>
  </Modal>
</template>
