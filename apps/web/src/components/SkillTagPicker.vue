<script setup lang="ts">
import { computed } from "vue";
import { tagKey, tagLabel } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../types";

const props = withDefaults(
  defineProps<{
    value: SkillTagPayload[];
    groups: TagGroup[];
    disabled?: boolean;
  }>(),
  { disabled: false },
);
const emit = defineEmits<{ change: [tags: SkillTagPayload[]] }>();

const selected = computed(() => new Set(props.value.map(tagKey)));
const hasValues = computed(() => props.groups.some((group) => group.values.length > 0));

function toggle(groupId: string, value: string): void {
  if (props.disabled) return;
  const key = tagKey({ group_id: groupId, value });
  const next = props.value.filter((tag) => tagKey(tag) !== key);
  if (!selected.value.has(key)) next.push({ group_id: groupId, value });
  emit("change", next);
}
</script>

<template>
  <div class="skill-tag-picker">
    <p v-if="!groups.length" class="field-help">还没有 Tag Group。请先在后台管理页维护可选 Tag。</p>
    <p v-else-if="!hasValues" class="field-help">Tag Group 中还没有可选 Tag。请先在后台管理页添加 Tag 值。</p>
    <div v-for="group in groups" :key="group.id" class="skill-tag-group">
      <div class="skill-tag-group-title">
        <strong>{{ group.display_name }}</strong>
        <code>{{ group.id }}</code>
      </div>
      <p v-if="group.description" class="field-help">{{ group.description }}</p>
      <div v-if="group.values.length" class="skill-tag-options">
        <label v-for="option in group.values" :key="option.value" class="skill-tag-option" :class="{ selected: selected.has(tagKey({ group_id: group.id, value: option.value })) }">
          <input
            type="checkbox"
            :disabled="disabled"
            :checked="selected.has(tagKey({ group_id: group.id, value: option.value }))"
            @change="toggle(group.id, option.value)"
          />
          <span>{{ tagLabel({ group_id: group.id, value: option.value, value_display_name: option.display_name }, groups) }}</span>
        </label>
      </div>
      <p v-else class="field-help">这个 Tag Group 还没有可选值。</p>
    </div>
  </div>
</template>
