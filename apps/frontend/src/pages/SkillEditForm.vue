<script setup lang="ts">
import { computed, ref } from "vue";
import BundleEditor from "../components/BundleEditor.vue";
import VersionSelector from "../components/VersionSelector.vue";
import { api, ApiError } from "../lib/api";
import { nextPatchVersion, validSemver } from "../lib/semver";
import {
  buildBundleSourceFromDraftFiles,
  bundleFilesToDraftFiles,
  defaultSkillBundleDraftFile,
  SKILL_ENTRY_PATH,
  validateBundleDraftFiles,
} from "../lib/skillBundleDraft";
import type { SkillDetail, SkillVersion } from "../types";

const props = withDefaults(defineProps<{ skill: SkillDetail; version: SkillVersion; actionsClassName?: string }>(), { actionsClassName: "modal-actions" });
const emit = defineEmits<{ cancel: []; saved: [] }>();

const files = computed(() => props.version.bundle_files ?? []);
const draftFiles = ref(bundleFilesToDraftFiles(files.value));
const validation = computed(() => validateBundleDraftFiles(draftFiles.value));
const entryFile = computed(() => draftFiles.value.find((file) => file.path.trim() === SKILL_ENTRY_PATH) ?? null);
const version = ref(nextPatchVersion(props.skill.versions));
const displayName = ref("");
const changeSummary = ref(`基于 ${versionLabel(props.version)} 编辑 Skill 内容。`);
const busy = ref(false);
const error = ref<string | null>(null);
const canSubmit = computed(
  () =>
    !busy.value &&
    validSemver(version.value) &&
    validation.value.valid &&
    Boolean(entryFile.value && !entryFile.value.binary && entryFile.value.content_text?.trim() && changeSummary.value.trim()),
);

async function submit(): Promise<void> {
  busy.value = true;
  error.value = null;
  try {
    await api.createSkillVersion({
      skill_id: props.skill.skill.id,
      source: buildBundleSourceFromDraftFiles(draftFiles.value, props.skill.skill.slug),
      make_current: true,
      version: version.value.trim(),
      display_name: cleanOptional(displayName.value),
      change_summary: changeSummary.value.trim(),
    });
    emit("saved");
  } catch (caught) {
    error.value = caught instanceof ApiError || caught instanceof Error ? caught.message : "保存失败。";
  } finally {
    busy.value = false;
  }
}

function cleanOptional(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}

function versionLabel(version: SkillVersion): string {
  return version.display_name?.trim() || version.version || `v${version.version_number}`;
}

/** 添加一个新的文本文件，并交给 BundleEditor 自动选中。 */
function addFile(): void {
  draftFiles.value = [...draftFiles.value, defaultSkillBundleDraftFile(draftFiles.value)];
}

/** 删除非入口文件。 */
function removeFile(id: string): void {
  draftFiles.value = draftFiles.value.filter((file) => file.id !== id || file.path.trim() === SKILL_ENTRY_PATH);
}

/** 更新文件路径，保存前会统一校验。 */
function updatePath(id: string, path: string): void {
  draftFiles.value = draftFiles.value.map((file) => (file.id === id ? { ...file, path } : file));
}

/** 更新文本文件内容。 */
function updateContent(id: string, content: string): void {
  draftFiles.value = draftFiles.value.map((file) => (file.id === id && !file.binary ? { ...file, content_text: content } : file));
}
</script>

<template>
  <div class="form-stack skill-edit-form">
    <div v-if="error" class="form-error">{{ error }}</div>
    <div class="hint-strip">保存后会追加新的 Skill 版本，并设置为当前版本。</div>
    <div v-if="!entryFile" class="form-error">当前 bundle 找不到根目录 SKILL.md，无法使用页面编辑。</div>
    <div v-if="entryFile?.binary" class="form-error">SKILL.md 不是可编辑文本文件。</div>
    <div v-for="globalError in validation.globalErrors" :key="globalError" class="form-error">{{ globalError }}</div>
    <VersionSelector v-model="version" :versions="skill.versions" />
    <label class="field-label">
      <span>版本名称</span>
      <input v-model="displayName" maxlength="80" :placeholder="`例如 ${skill.skill.slug} edited`" />
    </label>
    <label class="field-label">
      <span>版本说明</span>
      <input v-model="changeSummary" maxlength="500" />
    </label>
    <BundleEditor
      :files="draftFiles"
      :validation="validation"
      :root-label="skill.skill.slug"
      @add="addFile"
      @remove="removeFile"
      @path-change="updatePath"
      @content-change="updateContent"
    />
    <div :class="actionsClassName">
      <button class="secondary-button" type="button" @click="emit('cancel')">取消</button>
      <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
        {{ busy ? "保存中..." : "保存为新版本" }}
      </button>
    </div>
  </div>
</template>
