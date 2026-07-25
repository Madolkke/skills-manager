<script setup lang="ts">
import { AlertTriangle, Save } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { api, ApiError } from "../../lib/api";
import { validateSkillSlug } from "../../lib/skillBundleDraft";
import type { SkillRecord, ToastState } from "../../types";

const props = defineProps<{ skill: SkillRecord; canEdit: boolean }>();
const emit = defineEmits<{ refresh: []; toast: [toast: ToastState] }>();

const slug = ref(props.skill.slug);
const displayName = ref(props.skill.display_name ?? "");
const busy = ref(false);

watch(() => props.skill, reset, { deep: true });

const slugError = computed(() => validateSkillSlug(slug.value));
const slugChanged = computed(() => slug.value.trim() !== props.skill.slug);
const normalizedDisplayName = computed(() => displayName.value.trim());
const changed = computed(() => slugChanged.value || normalizedDisplayName.value !== (props.skill.display_name ?? ""));
const canSave = computed(() => props.canEdit && !busy.value && !slugError.value && changed.value);

function reset(): void {
  slug.value = props.skill.slug;
  displayName.value = props.skill.display_name ?? "";
}

async function save(): Promise<void> {
  if (!canSave.value) return;
  busy.value = true;
  try {
    await api.updateSkill(props.skill.id, {
      slug: slug.value.trim(),
      expected_slug: props.skill.slug,
      owner_ref: props.skill.owner_ref,
      display_name: normalizedDisplayName.value || null,
    });
    emit("toast", {
      tone: "success",
      message: slugChanged.value ? "Skill ID 已更新，并生成新的 Patch 版本。" : "Skill 中文名已更新。",
    });
    emit("refresh");
  } catch (error) {
    emit("toast", {
      tone: "danger",
      message: error instanceof ApiError || error instanceof Error ? error.message : "基本信息保存失败。",
    });
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="settings-section general-settings-section">
    <div class="settings-section-header">
      <div>
        <h3>基本信息</h3>
        <p>Skill ID 是主要标识；中文名仅用于辅助辨识。</p>
      </div>
      <button class="primary-button" type="button" :disabled="!canSave" @click="save">
        <Save :size="16" />{{ busy ? "保存中" : "保存" }}
      </button>
    </div>

    <div v-if="!canEdit" class="settings-notice muted">需要 maintainer、owner 或 admin 权限才能修改基本信息。</div>
    <div class="general-settings-form">
      <label class="field-label">
        <span>内部 ID</span>
        <input :value="skill.id" disabled aria-label="稳定内部 ID" />
        <small>稳定引用，不会随 Skill ID 重命名而变化。</small>
      </label>
      <label class="field-label">
        <span>Skill ID</span>
        <input v-model="slug" maxlength="64" :disabled="!canEdit || busy" aria-label="Skill ID" />
        <small v-if="slugError" class="danger">{{ slugError }}</small>
      </label>
      <label class="field-label">
        <span>中文名（可选）</span>
        <input v-model="displayName" maxlength="120" :disabled="!canEdit || busy" placeholder="例如 BGP 会话故障排查" />
        <small>不要求唯一，留空即可清除。</small>
      </label>
    </div>

    <div v-if="slugChanged" class="rename-skill-warning">
      <AlertTriangle :size="18" />
      <p>重命名会自动生成新的 Patch 版本，并更新当前 SKILL.md。已发布的外部目录不会自动移动或删除。</p>
    </div>
  </section>
</template>
