<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { orphanedTags, pruneInactiveTags, rootTagGroups, selectedLeafTags, tagValuePathLabel } from "../lib/tagCascades";
import { missingRequiredTagGroups, requiredTagMissingMessage, tagKey } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../types";
import SkillTagBranchEditor from "./SkillTagBranchEditor.vue";

const props = withDefaults(
  defineProps<{
    value: SkillTagPayload[];
    groups: TagGroup[];
    disabled?: boolean;
    mode?: "inline" | "staged";
  }>(),
  { disabled: false, mode: "staged" },
);
const emit = defineEmits<{ change: [tags: SkillTagPayload[]]; done: [tags: SkillTagPayload[]] }>();
const editing = ref(props.mode === "inline");
const draft = ref<SkillTagPayload[]>(props.value.map((tag) => ({ ...tag })));
const validationError = ref("");
const cleanupMessage = ref("");
const sourceTags = computed(() => (props.mode === "inline" ? props.value : editing.value ? draft.value : props.value));
const roots = computed(() => rootTagGroups(props.groups));
const orphanTags = computed(() => orphanedTags(sourceTags.value, props.groups));
const orphanKeys = computed(() => new Set(orphanTags.value.map(tagKey)));
const missingRequiredGroups = computed(() => missingRequiredTagGroups(sourceTags.value, props.groups));
const firstMissingGroupId = computed(() => missingRequiredGroups.value[0]?.id ?? "");
const selectedTags = computed(() => {
  const seen = new Set<string>();
  return [...selectedLeafTags(sourceTags.value, props.groups), ...orphanTags.value]
    .filter((tag) => {
      const key = tagKey(tag);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((tag) => ({
      ...tag,
      label: tagValuePathLabel(props.groups, tag.group_id, tag.value),
      pathValid: !orphanKeys.value.has(tagKey(tag)),
    }));
});

watch(() => props.disabled, (disabled) => {
  if (disabled && props.mode === "staged") cancelEdit();
});
watch(() => props.value, (value) => {
  if (props.mode === "staged" && !editing.value) draft.value = value.map((tag) => ({ ...tag }));
}, { deep: true });
watch(() => props.mode, (mode) => {
  editing.value = mode === "inline";
});

function startEdit(): void {
  if (props.disabled) return;
  draft.value = props.value.map((tag) => ({ ...tag }));
  validationError.value = "";
  cleanupMessage.value = "";
  editing.value = true;
}

function finishEdit(): void {
  const message = requiredTagMissingMessage(draft.value, props.groups);
  if (orphanedTags(draft.value, props.groups).length) {
    validationError.value = "存在路径失效的 Tag，请补齐父级选择或移除警告 Tag。";
    return;
  }
  if (message) {
    validationError.value = message;
    return;
  }
  const next = draft.value.map((tag) => ({ ...tag }));
  editing.value = false;
  validationError.value = "";
  cleanupMessage.value = "";
  emit("change", next);
  emit("done", next);
}

function cancelEdit(): void {
  editing.value = false;
  draft.value = props.value.map((tag) => ({ ...tag }));
  validationError.value = "";
  cleanupMessage.value = "";
}

function toggle(groupId: string, value: string): void {
  if (props.disabled || (props.mode === "staged" && !editing.value)) return;
  const current = sourceTags.value.map((tag) => ({ ...tag }));
  const key = tagKey({ group_id: groupId, value });
  const removing = current.some((tag) => tagKey(tag) === key);
  const changed = removing
    ? current.filter((tag) => tagKey(tag) !== key)
    : [...current, { group_id: groupId, value }];
  const next = removing ? pruneInactiveTags(changed, props.groups) : changed;
  const removedCount = current.length - next.length;
  cleanupMessage.value = removing && removedCount > 1 ? `已同时移除 ${removedCount - 1} 个下级 Tag。` : "";
  validationError.value = "";
  applyTags(next);
}

function updateFreeValues(groupId: string, values: string[]): void {
  const next = sourceTags.value.filter((tag) => tag.group_id !== groupId);
  next.push(...values.map((value) => ({ group_id: groupId, value })));
  validationError.value = "";
  cleanupMessage.value = "";
  applyTags(next);
}

function removeTag(tag: SkillTagPayload): void {
  const next = pruneInactiveTags(sourceTags.value.filter((item) => tagKey(item) !== tagKey(tag)), props.groups);
  applyTags(next);
}

function applyTags(tags: SkillTagPayload[]): void {
  const next = tags.map((tag) => ({ ...tag }));
  if (props.mode === "inline") emit("change", next);
  else draft.value = next;
}
</script>

<template>
  <div class="skill-tag-picker">
    <div class="skill-tag-toolbar">
      <div class="skill-tag-selected">
        <span
          v-for="tag in selectedTags"
          :key="tagKey(tag)"
          :class="['tag-chip', 'editable', { warning: !tag.pathValid }]"
          :title="tag.pathValid ? tag.label : `${tag.label}（路径失效）`"
        >
          <span class="tag-chip-label">{{ tag.label }}</span>
          <button v-if="(mode === 'inline' || editing) && !disabled" type="button" :aria-label="`移除 ${tag.label}`" @click="removeTag(tag)">×</button>
        </span>
        <span v-for="group in missingRequiredGroups" :key="`missing-${group.id}`" class="tag-chip warning">缺少：{{ group.display_name }}</span>
        <span v-if="!selectedTags.length" class="tag-chip muted">尚未添加 Tag</span>
      </div>

      <div v-if="!disabled && mode === 'staged'" class="button-row">
        <button v-if="!editing" class="secondary-button" type="button" :disabled="!roots.length" @click="startEdit">编辑 Tags</button>
        <template v-else>
          <button class="primary-button" type="button" @click="finishEdit">完成</button>
          <button class="secondary-button" type="button" @click="cancelEdit">取消</button>
        </template>
      </div>
    </div>

    <p v-if="!groups.length" class="field-help">还没有 Tag Group。请先在后台管理页维护可选 Tag。</p>
    <p v-if="validationError" class="field-hint danger">{{ validationError }}</p>
    <p v-if="cleanupMessage" class="field-hint">{{ cleanupMessage }}</p>

    <div v-if="(mode === 'inline' || editing) && roots.length" class="skill-tag-branch-list">
      <SkillTagBranchEditor
        v-for="group in roots"
        :key="group.id"
        :group="group"
        :groups="groups"
        :tags="sourceTags"
        :disabled="disabled"
        :missing-group-id="firstMissingGroupId"
        @toggle="toggle"
        @update-free="updateFreeValues"
      />
    </div>
  </div>
</template>
