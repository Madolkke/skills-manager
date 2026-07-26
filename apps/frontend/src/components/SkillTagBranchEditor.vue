<script setup lang="ts">
import { computed } from "vue";
import { childGroupsForValue, sortTagValues, tagGroupPathLabel } from "../lib/tagCascades";
import { tagKey } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../types";
import SkillTagFreeInput from "./SkillTagFreeInput.vue";

defineOptions({ name: "SkillTagBranchEditor" });

const props = defineProps<{
  group: TagGroup;
  groups: TagGroup[];
  tags: SkillTagPayload[];
  disabled: boolean;
  missingGroupId?: string;
  depth?: number;
}>();
const emit = defineEmits<{
  toggle: [groupId: string, value: string];
  updateFree: [groupId: string, values: string[]];
}>();
const selectedKeys = computed(() => new Set(props.tags.map(tagKey)));
const values = computed(() => sortTagValues(props.group));
const freeValues = computed(() => props.tags.filter((tag) => tag.group_id === props.group.id).map((tag) => tag.value));
const pathLabel = computed(() => tagGroupPathLabel(props.groups, props.group.id));

function selected(value: string): boolean {
  return selectedKeys.value.has(tagKey({ group_id: props.group.id, value }));
}

function forwardToggle(groupId: string, value: string): void {
  emit("toggle", groupId, value);
}

function forwardFreeValues(groupId: string, values: string[]): void {
  emit("updateFree", groupId, values);
}
</script>

<template>
  <section :class="['skill-tag-branch', { nested: (depth ?? 0) > 0, missing: missingGroupId === group.id }]" :aria-label="pathLabel">
    <header class="skill-tag-branch-head">
      <div>
        <strong>{{ group.display_name }}</strong>
        <small v-if="group.parent">{{ pathLabel }}</small>
      </div>
      <div class="admin-chip-list">
        <span :class="['tag-chip', group.required ? 'warning' : 'muted']">{{ group.required ? "必选" : "可选" }}</span>
        <span class="tag-chip muted">{{ group.free_form ? "自由输入" : "枚举" }}</span>
      </div>
    </header>
    <p v-if="group.description" class="skill-tag-branch-description">{{ group.description }}</p>

    <SkillTagFreeInput
      v-if="group.free_form"
      :group="group"
      :values="freeValues"
      :disabled="disabled"
      @change="emit('updateFree', group.id, $event)"
    />
    <div v-else class="skill-tag-branch-values">
      <div v-for="option in values" :key="option.value" class="skill-tag-value-branch">
        <label :class="['skill-tag-option', { selected: selected(option.value) }]" :title="option.value">
          <input
            type="checkbox"
            :checked="selected(option.value)"
            :disabled="disabled"
            @change="emit('toggle', group.id, option.value)"
          />
          <span class="skill-tag-option-copy">
            <strong>{{ option.display_name || option.value }}</strong>
            <small v-if="option.display_name">{{ option.value }}</small>
          </span>
        </label>
        <div v-if="selected(option.value)" class="skill-tag-branch-children">
          <SkillTagBranchEditor
            v-for="child in childGroupsForValue(groups, group.id, option.value)"
            :key="child.id"
            :group="child"
            :groups="groups"
            :tags="tags"
            :disabled="disabled"
            :missing-group-id="missingGroupId"
            :depth="(depth ?? 0) + 1"
            @toggle="forwardToggle"
            @update-free="forwardFreeValues"
          />
        </div>
      </div>
      <p v-if="!values.length" class="field-help">这个枚举组还没有候选值。</p>
    </div>
  </section>
</template>
