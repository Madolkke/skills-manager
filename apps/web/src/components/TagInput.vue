<script setup lang="ts">
import { X } from "lucide-vue-next";
import { computed, ref } from "vue";

const props = withDefaults(defineProps<{ value: string[]; suggestions?: string[]; placeholder?: string }>(), {
  suggestions: () => [],
  placeholder: "输入 tag 后按 Enter",
});
const emit = defineEmits<{ change: [tags: string[]] }>();

const draft = ref("");
const available = computed(() => props.suggestions.filter((tag) => !props.value.includes(tag) && tag.toLowerCase().includes(draft.value.toLowerCase())).slice(0, 6));

function addTag(raw: string): void {
  const tag = raw.trim();
  if (!tag || props.value.includes(tag)) return;
  emit("change", [...props.value, tag]);
  draft.value = "";
}
</script>

<template>
  <div class="tag-input">
    <div class="tag-box">
      <span v-for="tag in value" :key="tag" class="tag-chip editable">
        {{ tag }}
        <button type="button" :aria-label="`移除 ${tag}`" @click="emit('change', value.filter((item) => item !== tag))">
          <X :size="13" />
        </button>
      </span>
      <input
        v-model="draft"
        :placeholder="value.length === 0 ? placeholder : ''"
        @keydown.enter.prevent="addTag(draft)"
        @keydown.,.prevent="addTag(draft)"
        @keydown.backspace="() => { if (!draft && value.length > 0) emit('change', value.slice(0, -1)); }"
        @blur="addTag(draft)"
      >
    </div>
    <div v-if="available.length > 0" class="tag-suggestions">
      <button
        v-for="tag in available"
        :key="tag"
        type="button"
        @mousedown.prevent
        @click="addTag(tag)"
      >
        {{ tag }}
      </button>
    </div>
  </div>
</template>
