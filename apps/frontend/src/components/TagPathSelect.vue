<script setup lang="ts">
import { AlertTriangle, Check, ChevronDown, Search } from "lucide-vue-next";
import { computed, ref } from "vue";
import { sortGroups, sortTagValues, tagValuePathInfo } from "../lib/tagCascades";
import { tagKey } from "../lib/skillTags";
import type { SkillTagPayload, TagGroup } from "../types";

const props = withDefaults(defineProps<{
  groups: TagGroup[];
  modelValue: SkillTagPayload | null;
  placeholder?: string;
  disabled?: boolean;
}>(), { placeholder: "选择 Tag 路径", disabled: false });
const emit = defineEmits<{ "update:modelValue": [tag: SkillTagPayload] }>();
const open = ref(false);
const query = ref("");
const host = ref<HTMLElement | null>(null);
const options = computed(() => sortGroups(props.groups).flatMap((group) => sortTagValues(group).map((value) => {
  const path = tagValuePathInfo(props.groups, group.id, value.value);
  return {
    tag: { group_id: group.id, value: value.value },
    label: path.segments.map((segment) => segment.label).join(" / "),
    code: `${group.id} / ${value.value}`,
    valid: path.valid,
  };
})));
const visibleOptions = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  if (!keyword) return options.value;
  return options.value.filter((option) => `${option.label} ${option.code}`.toLowerCase().includes(keyword));
});
const selectedOption = computed(() => props.modelValue
  ? options.value.find((option) => tagKey(option.tag) === tagKey(props.modelValue!)) ?? null
  : null);

function select(tag: SkillTagPayload): void {
  emit("update:modelValue", tag);
  open.value = false;
  query.value = "";
}

function handleFocusout(event: FocusEvent): void {
  if (!host.value?.contains(event.relatedTarget as Node | null)) open.value = false;
}
</script>

<template>
  <div ref="host" class="tag-path-select" @focusout="handleFocusout" @keydown.esc="open = false">
    <button
      class="tag-path-select-trigger"
      type="button"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span :class="{ muted: !selectedOption, warning: selectedOption && !selectedOption.valid }">
        {{ selectedOption?.label || placeholder }}
        <small v-if="selectedOption && !selectedOption.valid">路径失效</small>
      </span>
      <ChevronDown :size="16" />
    </button>
    <div v-if="open" class="tag-path-select-popover">
      <label class="search-field tag-path-select-search">
        <Search :size="15" />
        <input v-model="query" autofocus placeholder="搜索路径、Group 或 Tag" aria-label="搜索 Tag 路径" />
      </label>
      <div class="tag-path-select-options" role="listbox">
        <button
          v-for="option in visibleOptions"
          :key="tagKey(option.tag)"
          :class="['tag-path-select-option', { selected: modelValue && tagKey(modelValue) === tagKey(option.tag) }]"
          type="button"
          role="option"
          :aria-selected="Boolean(modelValue && tagKey(modelValue) === tagKey(option.tag))"
          @click="select(option.tag)"
        >
          <span><strong>{{ option.label }}</strong><small>{{ option.code }}{{ option.valid ? "" : " · 路径失效" }}</small></span>
          <AlertTriangle v-if="!option.valid" :size="16" class="warning-icon" />
          <Check v-else-if="modelValue && tagKey(modelValue) === tagKey(option.tag)" :size="16" />
        </button>
        <p v-if="!visibleOptions.length" class="field-help">没有匹配的 Tag 路径。</p>
      </div>
    </div>
  </div>
</template>
