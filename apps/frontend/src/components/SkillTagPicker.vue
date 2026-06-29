<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { missingRequiredTagGroups, requiredTagMissingMessage, sortTagGroupsForPicker, tagKey, tagLabel } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup, TagValueOption } from "../types";

const props = withDefaults(
  defineProps<{
    value: SkillTagPayload[];
    groups: TagGroup[];
    disabled?: boolean;
  }>(),
  { disabled: false },
);
const emit = defineEmits<{
  change: [tags: SkillTagPayload[]];
  done: [tags: SkillTagPayload[]];
}>();

const editing = ref(false);
const activeGroupId = ref("");
const draft = ref<SkillTagPayload[]>([]);
const validationError = ref("");

const sourceTags = computed(() => (editing.value ? draft.value : props.value));
const selected = computed(() => new Set(sourceTags.value.map(tagKey)));
const sortedGroups = computed(() => sortTagGroupsForPicker(props.groups));
const groupsWithValues = computed(() => sortedGroups.value.filter((group) => group.values.length > 0));
const hasValues = computed(() => groupsWithValues.value.length > 0);
const activeGroup = computed(() => groupsWithValues.value.find((group) => group.id === activeGroupId.value) ?? groupsWithValues.value[0] ?? null);
const activeValues = computed(() => sortValues(activeGroup.value?.values ?? []));
const selectedTags = computed(() => decorateTags(sourceTags.value));
const missingRequiredGroups = computed(() => missingRequiredTagGroups(sourceTags.value, props.groups));

watch(groupsWithValues, (groups) => {
  if (!groups.length) {
    activeGroupId.value = "";
    editing.value = false;
    return;
  }
  if (!groups.some((group) => group.id === activeGroupId.value)) activeGroupId.value = preferredActiveGroupId(sourceTags.value);
}, { immediate: true });

watch(() => props.disabled, (disabled) => {
  if (disabled) cancelEdit();
});

watch(() => props.value, (value) => {
  if (!editing.value) draft.value = [...value];
}, { deep: true });

function decorateTags(tags: SkillTagPayload[]): Array<SkillTagPayload & { label: string; groupOrder: number }> {
  return tags
    .map((tag) => {
      const group = props.groups.find((item) => item.id === tag.group_id);
      const value = group?.values.find((item) => item.value === tag.value);
      return { ...tag, label: tagLabel({ ...tag, value_display_name: value?.display_name }, props.groups), groupOrder: group?.sort_order ?? 0 };
    })
    .sort((a, b) => a.groupOrder - b.groupOrder || a.label.localeCompare(b.label));
}

function sortValues(values: TagValueOption[]): TagValueOption[] {
  return [...values].sort((a, b) => a.sort_order - b.sort_order || optionLabel(a).localeCompare(optionLabel(b)));
}

function optionLabel(option: TagValueOption): string {
  return option.display_name?.trim() || option.value;
}

function startEdit(): void {
  if (props.disabled) return;
  draft.value = props.value.map((tag) => ({ ...tag }));
  activeGroupId.value = preferredActiveGroupId(draft.value);
  validationError.value = "";
  editing.value = true;
}

function finishEdit(): void {
  const next = draft.value.map((tag) => ({ ...tag }));
  const message = requiredTagMissingMessage(next, props.groups);
  if (message) {
    validationError.value = message;
    activeGroupId.value = missingRequiredTagGroups(next, props.groups)[0]?.id ?? activeGroupId.value;
    return;
  }
  editing.value = false;
  validationError.value = "";
  emit("change", next);
  emit("done", next);
}

function cancelEdit(): void {
  editing.value = false;
  draft.value = props.value.map((tag) => ({ ...tag }));
  validationError.value = "";
}

function toggle(groupId: string, value: string): void {
  if (props.disabled || !editing.value) return;
  validationError.value = "";
  const key = tagKey({ group_id: groupId, value });
  const next = draft.value.filter((tag) => tagKey(tag) !== key);
  if (!selected.value.has(key)) next.push({ group_id: groupId, value });
  draft.value = next;
}

function removeTag(tag: SkillTagPayload): void {
  if (props.disabled || !editing.value) return;
  validationError.value = "";
  draft.value = draft.value.filter((item) => tagKey(item) !== tagKey(tag));
}

function preferredActiveGroupId(tags: SkillTagPayload[]): string {
  const missing = missingRequiredTagGroups(tags, props.groups)[0];
  if (missing) return missing.id;
  const required = groupsWithValues.value.find((group) => group.required);
  return required?.id ?? groupsWithValues.value[0]?.id ?? "";
}
</script>

<template>
  <div class="skill-tag-picker">
    <div class="skill-tag-toolbar">
      <div class="skill-tag-selected">
        <span v-for="tag in selectedTags" :key="tagKey(tag)" class="tag-chip editable">
          {{ tag.label }}
          <button v-if="editing && !disabled" type="button" :aria-label="`移除 ${tag.label}`" @click="removeTag(tag)">×</button>
        </span>
        <span v-for="group in missingRequiredGroups" :key="`missing-${group.id}`" class="tag-chip warning">缺少：{{ group.display_name }}</span>
        <span v-if="!selectedTags.length" class="tag-chip muted">尚未添加 Tag</span>
      </div>

      <div v-if="!disabled" class="button-row">
        <button v-if="!editing" class="secondary-button" type="button" :disabled="!hasValues" @click="startEdit">编辑 Tags</button>
        <template v-else>
          <button class="primary-button" type="button" @click="finishEdit">完成</button>
          <button class="secondary-button" type="button" @click="cancelEdit">取消</button>
        </template>
      </div>
    </div>

    <p v-if="!groups.length" class="field-help">还没有 Tag Group。请先在后台管理页维护可选 Tag。</p>
    <p v-if="validationError" class="field-hint danger">{{ validationError }}</p>

    <section v-if="editing && activeGroup" class="skill-tag-add-panel">
      <label class="field-label compact">
        <span>选择 Tag Group</span>
        <select v-model="activeGroupId">
          <option v-for="group in groupsWithValues" :key="group.id" :value="group.id">
            {{ group.display_name }}{{ group.required ? "（必选）" : "" }}
          </option>
        </select>
      </label>

      <div class="skill-tag-add-options">
        <label
          v-for="option in activeValues"
          :key="option.value"
          class="skill-tag-option"
          :class="{ selected: selected.has(tagKey({ group_id: activeGroup.id, value: option.value })) }"
        >
          <input
            type="checkbox"
            :checked="selected.has(tagKey({ group_id: activeGroup.id, value: option.value }))"
            @change="toggle(activeGroup.id, option.value)"
          />
          <span>{{ optionLabel(option) }}</span>
        </label>
      </div>
      <p v-if="activeGroup.description" class="field-help">{{ activeGroup.description }}</p>
    </section>
  </div>
</template>
