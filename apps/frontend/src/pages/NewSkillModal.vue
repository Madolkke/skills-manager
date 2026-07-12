<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import BundlePicker from "../components/BundlePicker.vue";
import Modal from "../components/Modal.vue";
import SkillTagPicker from "../components/SkillTagPicker.vue";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";
import { validSemver } from "../lib/semver";
import { createBlankSkillSource, validateBlankSkillDraft, validateSkillSlug } from "../lib/skillBundleDraft";
import { requiredTagMissingMessage } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../types";

const props = defineProps<{ actor: string }>();
const emit = defineEmits<{ close: []; created: [skillId: string] }>();

const mode = ref<"upload" | "blank" | "workflow">("upload");
const folderFiles = ref<File[]>([]);
const zipFile = ref<File | null>(null);
const version = ref("0.0.1");
const slug = ref("");
const description = ref("");
const tags = ref<SkillTagPayload[]>([]);
const tagGroups = ref<TagGroup[]>([]);
const busy = ref(false);
const error = ref<string | null>(null);
const blankValidation = computed(() => validateBlankSkillDraft({ slug: slug.value, description: description.value }));
const tagValidationError = computed(() => requiredTagMissingMessage(tags.value, tagGroups.value));
const modalDescription = computed(() => {
  if (mode.value === "workflow") return "创建与 Workflow 永久绑定的 Skill，并生成 0.0.1 空白版本。";
  if (mode.value === "blank") return "创建只包含 SKILL.md 的空白 Skill，之后可在平台中继续添加文件。";
  return "上传标准 Skill bundle，名称和说明会从 SKILL.md frontmatter 读取。";
});
const canSubmit = computed(() => {
  if (busy.value || tagValidationError.value) return false;
  if (mode.value === "blank" || mode.value === "workflow") return blankValidation.value.valid && (mode.value === "workflow" || validSemver(version.value));
  if (!validSemver(version.value)) return false;
  return Boolean(zipFile.value || folderFiles.value.length);
});

onMounted(async () => {
  try {
    tagGroups.value = await api.listTagGroups();
  } catch {
    tagGroups.value = [];
  }
});

async function submit(): Promise<void> {
  busy.value = true;
  error.value = null;
  try {
    if (mode.value === "workflow") {
      const created = await api.createWorkflowSkill({
        slug: slug.value.trim(),
        owner_ref: props.actor,
        description: description.value.trim(),
        tags: tags.value,
      });
      emit("created", created.skill_id);
      return;
    }
    const source = mode.value === "blank"
      ? createBlankSkillSource({ slug: slug.value, description: description.value })
      : await sourceFromFiles(folderFiles.value, zipFile.value);
    const created = await api.importSkill({ owner_ref: props.actor, source, version: version.value.trim(), tags: tags.value });
    emit("created", created.skill_id);
  } catch (caught) {
    error.value = caught instanceof ApiError || caught instanceof Error ? caught.message : "创建失败。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Modal
    title="新建 Skill"
    :description="modalDescription"
    @close="emit('close')"
  >
    <div class="form-stack">
      <div v-if="error" class="form-error">{{ error }}</div>
      <div class="new-skill-mode-switch" role="tablist" aria-label="新建 Skill 方式">
        <button :class="['new-skill-mode-button', mode === 'upload' && 'active']" type="button" role="tab" :aria-selected="mode === 'upload'" @click="mode = 'upload'">
          上传 bundle
        </button>
        <button :class="['new-skill-mode-button', mode === 'blank' && 'active']" type="button" role="tab" :aria-selected="mode === 'blank'" @click="mode = 'blank'">
          空白创建
        </button>
        <button :class="['new-skill-mode-button', mode === 'workflow' && 'active']" type="button" role="tab" :aria-selected="mode === 'workflow'" @click="mode = 'workflow'">
          Workflow
        </button>
      </div>
      <template v-if="mode === 'blank' || mode === 'workflow'">
        <label class="field-label">
          <span>Skill ID</span>
          <input v-model="slug" maxlength="64" placeholder="例如 code-reviewer" />
        </label>
        <p v-if="slug.trim() && validateSkillSlug(slug)" class="field-hint danger">{{ validateSkillSlug(slug) }}</p>
        <label class="field-label">
          <span>Skill 描述</span>
          <textarea v-model="description" maxlength="1024" rows="3" placeholder="一句话说明这个 Skill 能完成什么任务" />
        </label>
        <p v-if="blankValidation.errors.description" class="field-hint danger">{{ blankValidation.errors.description }}</p>
      </template>
      <label v-if="mode !== 'workflow'" class="field-label">
        <span>初始版本号</span>
        <input v-model="version" maxlength="80" placeholder="例如 0.0.1" />
      </label>
      <p v-if="mode !== 'workflow' && version.trim() && !validSemver(version)" class="field-hint danger">版本号必须使用 SemVer，例如 0.0.1。</p>
      <div class="field-label new-skill-tags-field">
        <span>Skill Tags</span>
        <SkillTagPicker :value="tags" :groups="tagGroups" @change="tags = $event" />
      </div>
      <p v-if="tagValidationError" class="field-hint danger">{{ tagValidationError }}</p>
      <BundlePicker
        v-if="mode === 'upload'"
        @files="
          (nextFolderFiles, nextZipFile) => {
            folderFiles = nextFolderFiles;
            zipFile = nextZipFile;
          }
        "
      />
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
          {{ busy ? "创建中..." : "创建 Skill" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
