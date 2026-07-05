<script setup lang="ts">
import { computed, ref } from "vue";
import Modal from "../../../components/Modal.vue";
import SkillTagPicker from "../../../components/SkillTagPicker.vue";
import VersionSelector from "../../../components/VersionSelector.vue";
import { validSemver } from "../../../lib/semver";
import type { SkillBundleDraftFile } from "../../../lib/skillBundleDraft";
import { requiredTagMissingMessage } from "../../../lib/skillTags";
import type { SkillBuilderDraftFile, SkillTagPayload, TagGroup } from "../../../types";
import {
  builderSubmitMappingsFromFiles,
  builderSubmitPayloadFiles,
  validateBuilderSubmitMappings,
  type BuilderSubmitFileMapping,
} from "../lib/builderUi";

const props = defineProps<{
  files: SkillBundleDraftFile[];
  version: string;
  tags: SkillTagPayload[];
  tagGroups: TagGroup[];
  creating: boolean;
}>();

const emit = defineEmits<{
  close: [];
  "update:version": [version: string];
  "update:tags": [tags: SkillTagPayload[]];
  submit: [payload: { version: string; tags: SkillTagPayload[]; files: SkillBuilderDraftFile[] }];
}>();

const mappings = ref<BuilderSubmitFileMapping[]>(builderSubmitMappingsFromFiles(props.files));
const validation = computed(() => validateBuilderSubmitMappings(mappings.value));
const tagValidationError = computed(() => requiredTagMissingMessage(props.tags, props.tagGroups));
const canSubmit = computed(() => validation.value.valid && validSemver(props.version) && !tagValidationError.value && !props.creating);
const pathErrors = computed(() => {
  const errors: Record<string, string> = {};
  mappings.value.filter((item) => item.selected).forEach((item, index) => {
    const key = `submit-${index}-${item.id}`;
    if (validation.value.errors[key]) errors[item.id] = validation.value.errors[key];
  });
  return errors;
});
const selectedCount = computed(() => mappings.value.filter((item) => item.selected).length);

function updateMapping(id: string, patch: Partial<BuilderSubmitFileMapping>): void {
  mappings.value = mappings.value.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

function submit(): void {
  if (!canSubmit.value) return;
  emit("submit", {
    version: props.version.trim(),
    tags: props.tags,
    files: builderSubmitPayloadFiles(mappings.value),
  });
}
</script>

<template>
  <Modal title="提交 Skill" description="选择工作区文件并映射到正式 Skill bundle 路径。" size="wide" @close="emit('close')">
    <div class="builder-submit-modal">
      <div class="builder-submit-layout">
        <section class="builder-submit-files">
          <header>
            <div>
              <strong>提交文件</strong>
              <p class="field-hint">选择工作区文件，并映射到正式 Skill bundle 路径。</p>
            </div>
            <span class="builder-submit-count">已选择 {{ selectedCount }}/{{ mappings.length }}</span>
          </header>
          <div v-if="validation.globalErrors.length" class="form-error">{{ validation.globalErrors[0] }}</div>
          <div class="builder-submit-file-list">
            <article v-for="item in mappings" :key="item.id" :class="['builder-submit-file-row', !item.selected && 'muted']">
              <label class="checkbox-line">
                <input :checked="item.selected" type="checkbox" @change="updateMapping(item.id, { selected: ($event.target as HTMLInputElement).checked })" />
                <span>{{ item.sourcePath }}</span>
              </label>
              <label class="field-label compact">
                <span>正式路径</span>
                <input
                  :value="item.targetPath"
                  :disabled="!item.selected"
                  placeholder="例如 SKILL.md 或 references/guide.md"
                  @input="updateMapping(item.id, { targetPath: ($event.target as HTMLInputElement).value })"
                />
              </label>
              <p v-if="pathErrors[item.id]" class="field-hint danger">{{ pathErrors[item.id] }}</p>
            </article>
          </div>
        </section>

        <aside class="builder-submit-side">
          <section class="builder-submit-meta">
            <strong>Skill 信息</strong>
            <VersionSelector :model-value="version" :versions="[]" @update:model-value="emit('update:version', $event)" />
            <p v-if="version && !validSemver(version)" class="field-hint danger">版本号需要使用 SemVer，例如 0.1.0。</p>
            <div class="field-label new-skill-tags-field">
              <span>Skill Tags</span>
              <SkillTagPicker :value="tags" :groups="tagGroups" @change="emit('update:tags', $event)" />
            </div>
            <p v-if="tagValidationError" class="field-hint danger">{{ tagValidationError }}</p>
          </section>
        </aside>
      </div>

      <footer class="modal-actions builder-submit-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
          {{ creating ? "提交中..." : "提交 Skill" }}
        </button>
      </footer>
    </div>
  </Modal>
</template>
