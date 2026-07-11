<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { activeTagGroups, orphanedTags, pruneInactiveTags } from "../lib/tagCascades";
import { missingRequiredTagGroups, requiredTagMissingMessage, tagKey, tagLabel } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup, TagValueOption } from "../types";
import SkillTagFreeInput from "./SkillTagFreeInput.vue";

const props = withDefaults(
  defineProps<{ value: SkillTagPayload[]; groups: TagGroup[]; disabled?: boolean }>(),
  { disabled: false },
);
const emit = defineEmits<{ change: [tags: SkillTagPayload[]]; done: [tags: SkillTagPayload[]] }>();

const editing = ref(false);
const activeGroupId = ref("");
const draft = ref<SkillTagPayload[]>([]);
const validationError = ref("");

const sourceTags = computed(() => (editing.value ? draft.value : props.value));
const selected = computed(() => new Set(sourceTags.value.map(tagKey)));
const activeGroupItems = computed(() => activeTagGroups(props.groups, sourceTags.value));
const activeGroupItem = computed(() => activeGroupItems.value.find((item) => item.group.id === activeGroupId.value) ?? activeGroupItems.value[0] ?? null);
const activeGroup = computed(() => activeGroupItem.value?.group ?? null);
const activeValues = computed(() => sortValues(activeGroup.value?.values ?? []));
const activeFreeValues = computed(() => sourceTags.value.filter((tag) => tag.group_id === activeGroup.value?.id).map((tag) => tag.value));
const orphanKeys = computed(() => new Set(orphanedTags(sourceTags.value, props.groups).map(tagKey)));
const selectedTags = computed(() => decorateTags(sourceTags.value));
const missingRequiredGroups = computed(() => missingRequiredTagGroups(sourceTags.value, props.groups));

watch(activeGroupItems, (items) => {
  if (!items.length) {
    activeGroupId.value = "";
    editing.value = false;
    return;
  }
  if (!items.some((item) => item.group.id === activeGroupId.value)) activeGroupId.value = preferredActiveGroupId(sourceTags.value);
}, { immediate: true });

watch(() => props.disabled, (disabled) => {
  if (disabled) cancelEdit();
});

watch(() => props.value, (value) => {
  if (!editing.value) draft.value = value.map((tag) => ({ ...tag }));
}, { deep: true });

function decorateTags(tags: SkillTagPayload[]) {
  return tags
    .map((tag) => {
      const group = props.groups.find((item) => item.id === tag.group_id);
      const value = group?.values.find((item) => item.value === tag.value);
      return {
        ...tag,
        label: tagLabel({ ...tag, value_display_name: value?.display_name }, props.groups),
        groupOrder: group?.sort_order ?? 0,
        pathValid: !orphanKeys.value.has(tagKey(tag)),
      };
    })
    .sort((left, right) => left.groupOrder - right.groupOrder || left.label.localeCompare(right.label));
}

function sortValues(values: TagValueOption[]): TagValueOption[] {
  return [...values].sort((left, right) => left.sort_order - right.sort_order || optionLabel(left).localeCompare(optionLabel(right)));
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
  const orphaned = orphanedTags(draft.value, props.groups);
  if (orphaned.length) {
    validationError.value = "存在路径失效的 Tag，请补齐父级选择或移除警告 Tag。";
    return;
  }
  const message = requiredTagMissingMessage(draft.value, props.groups);
  if (message) {
    validationError.value = message;
    activeGroupId.value = missingRequiredTagGroups(draft.value, props.groups)[0]?.id ?? activeGroupId.value;
    return;
  }
  const next = draft.value.map((tag) => ({ ...tag }));
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
  const removing = selected.value.has(key);
  const next = draft.value.filter((tag) => tagKey(tag) !== key);
  if (!removing) next.push({ group_id: groupId, value });
  draft.value = removing ? pruneInactiveTags(next, props.groups) : next;
}

function updateFreeValues(values: string[]): void {
  if (!activeGroup.value) return;
  const next = draft.value.filter((tag) => tag.group_id !== activeGroup.value?.id);
  next.push(...values.map((value) => ({ group_id: activeGroup.value!.id, value })));
  draft.value = next;
  validationError.value = "";
}

function removeTag(tag: SkillTagPayload): void {
  if (props.disabled || !editing.value) return;
  draft.value = pruneInactiveTags(draft.value.filter((item) => tagKey(item) !== tagKey(tag)), props.groups);
  validationError.value = "";
}

function preferredActiveGroupId(tags: SkillTagPayload[]): string {
  return missingRequiredTagGroups(tags, props.groups)[0]?.id ?? activeGroupItems.value[0]?.group.id ?? "";
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
          <button v-if="editing && !disabled" type="button" :aria-label="`移除 ${tag.label}`" @click="removeTag(tag)">×</button>
        </span>
        <span v-for="group in missingRequiredGroups" :key="`missing-${group.id}`" class="tag-chip warning">缺少：{{ group.display_name }}</span>
        <span v-if="!selectedTags.length" class="tag-chip muted">尚未添加 Tag</span>
      </div>

      <div v-if="!disabled" class="button-row">
        <button v-if="!editing" class="secondary-button" type="button" :disabled="!activeGroupItems.length" @click="startEdit">编辑 Tags</button>
        <template v-else>
          <button class="primary-button" type="button" @click="finishEdit">完成</button>
          <button class="secondary-button" type="button" @click="cancelEdit">取消</button>
        </template>
      </div>
    </div>

    <p v-if="!groups.length" class="field-help">还没有 Tag Group。请先在后台管理页维护可选 Tag。</p>
    <p v-if="validationError" class="field-hint danger">{{ validationError }}</p>

    <section v-if="editing && activeGroup" class="skill-tag-add-panel">
      <div class="skill-tag-group-row">
        <label class="skill-tag-group-select">
          <span>选择 Tag Group</span>
          <select v-model="activeGroupId">
            <option v-for="item in activeGroupItems" :key="item.group.id" :value="item.group.id">
              {{ `${"  ".repeat(item.depth)}${item.depth ? "↳ " : ""}${item.group.display_name}${item.group.required ? "（必选）" : ""}` }}
            </option>
          </select>
        </label>
        <span :class="['tag-chip', activeGroup.required ? 'warning' : 'muted']">{{ activeGroup.required ? "必选" : "可选" }}</span>
        <span class="tag-chip muted">{{ activeGroup.free_form ? "自由输入" : "枚举" }}</span>
      </div>

      <SkillTagFreeInput
        v-if="activeGroup.free_form"
        :group="activeGroup"
        :values="activeFreeValues"
        :disabled="disabled"
        @change="updateFreeValues"
      />
      <div v-else class="skill-tag-add-options">
        <label
          v-for="option in activeValues"
          :key="option.value"
          class="skill-tag-option"
          :class="{ selected: selected.has(tagKey({ group_id: activeGroup.id, value: option.value })) }"
          :title="option.value"
        >
          <input
            type="checkbox"
            :checked="selected.has(tagKey({ group_id: activeGroup.id, value: option.value }))"
            @change="toggle(activeGroup.id, option.value)"
          />
          <span class="tag-chip-label">{{ optionLabel(option) }}</span>
        </label>
        <p v-if="!activeValues.length" class="field-help">这个枚举组还没有候选值。</p>
      </div>
      <p v-if="activeGroup.description" class="field-help">{{ activeGroup.description }}</p>
    </section>
  </div>
</template>
