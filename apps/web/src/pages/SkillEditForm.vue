<script setup lang="ts">
import { computed, ref } from "vue";
import BundleEditor from "../components/BundleEditor.vue";
import { api, ApiError } from "../lib/api";
import type { BundleFile, BundleSource, SkillDetail, SkillVersion } from "../types";

const ENTRY_PATH = "SKILL.md";

const props = withDefaults(defineProps<{ skill: SkillDetail; version: SkillVersion; actionsClassName?: string }>(), { actionsClassName: "modal-actions" });
const emit = defineEmits<{ cancel: []; saved: [] }>();

const files = computed(() => props.version.bundle_files ?? []);
const entryFile = computed(() => files.value.find((file) => file.path === ENTRY_PATH) ?? null);
const drafts = ref(textDrafts(files.value));
const displayName = ref("");
const changeSummary = ref(`基于 ${versionLabel(props.version)} 编辑 Skill 内容。`);
const busy = ref(false);
const error = ref<string | null>(null);
const missingBinaryContent = computed(() => files.value.some((file) => file.binary && !file.content_base64));
const canSubmit = computed(
  () => !busy.value && files.value.length > 0 && Boolean(entryFile.value && !entryFile.value.binary && drafts.value[ENTRY_PATH]?.trim() && changeSummary.value.trim() && !missingBinaryContent.value),
);

async function submit(): Promise<void> {
  busy.value = true;
  error.value = null;
  try {
    await api.createSkillVersion({
      skill_id: props.skill.skill.id,
      source: sourceFromBundle(files.value, drafts.value, props.skill.skill.slug),
      make_current: true,
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

function sourceFromBundle(bundleFiles: BundleFile[], values: Record<string, string>, slug: string): BundleSource {
  return {
    kind: "files",
    name: slug,
    files: bundleFiles.map((file) => filePayload(file, values)),
  };
}

function filePayload(file: BundleFile, values: Record<string, string>): { path: string; content_text?: string; content_base64?: string } {
  if (!file.binary) return { path: file.path, content_text: values[file.path] ?? file.content_text ?? "" };
  if (file.content_base64) return { path: file.path, content_base64: file.content_base64 };
  throw new Error(`当前 bundle 的二进制文件 ${file.path} 缺少内容，无法从页面编辑保存。`);
}

function textDrafts(bundleFiles: BundleFile[]): Record<string, string> {
  return Object.fromEntries(bundleFiles.filter((file) => !file.binary).map((file) => [file.path, file.content_text ?? ""]));
}

function cleanOptional(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}

function versionLabel(version: SkillVersion): string {
  return version.display_name?.trim() || `v${version.version_number}`;
}
</script>

<template>
  <div class="form-stack skill-edit-form">
    <div v-if="error" class="form-error">{{ error }}</div>
    <div class="hint-strip">保存后会追加新的 SkillVersion，并设置为当前版本。</div>
    <div v-if="!entryFile" class="form-error">当前 bundle 找不到根目录 SKILL.md，无法使用页面编辑。</div>
    <div v-if="entryFile?.binary" class="form-error">SKILL.md 不是可编辑文本文件。</div>
    <div v-if="missingBinaryContent" class="form-error">当前 bundle 有缺少内容的二进制文件，无法从页面编辑保存。</div>
    <label class="field-label">
      <span>版本名称</span>
      <input v-model="displayName" maxlength="80" :placeholder="`例如 ${skill.skill.slug} edited`" />
    </label>
    <label class="field-label">
      <span>版本说明</span>
      <input v-model="changeSummary" maxlength="500" />
    </label>
    <BundleEditor
      :files="files"
      :drafts="drafts"
      :root-label="skill.skill.slug"
      @draft-change="
        (path, content) => {
          drafts = { ...drafts, [path]: content };
        }
      "
    />
    <div :class="actionsClassName">
      <button class="secondary-button" type="button" @click="emit('cancel')">取消</button>
      <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
        {{ busy ? "保存中..." : "保存为新版本" }}
      </button>
    </div>
  </div>
</template>
