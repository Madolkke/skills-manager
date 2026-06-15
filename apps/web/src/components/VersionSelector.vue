<script setup lang="ts">
import { computed } from "vue";
import { bumpVersion, latestVersion, validSemver, type VersionBumpType } from "../lib/semver";
import type { SkillVersion } from "../types";

const props = defineProps<{ modelValue: string; versions: SkillVersion[] }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const current = computed(() => latestVersion(props.versions));
const options = computed(() => [
  { type: "major" as const, title: "重大", version: bumpVersion(current.value, "major"), detail: "接口或行为有破坏性变化" },
  { type: "minor" as const, title: "功能", version: bumpVersion(current.value, "minor"), detail: "新增能力且保持兼容" },
  { type: "patch" as const, title: "修订", version: bumpVersion(current.value, "patch"), detail: "修复、文案或小幅调整" },
]);
const selected = computed(() => options.value.find((item) => item.version === props.modelValue)?.type ?? null);
const invalid = computed(() => props.modelValue.trim() !== "" && !validSemver(props.modelValue));

function choose(type: VersionBumpType): void {
  emit("update:modelValue", bumpVersion(current.value, type));
}
</script>

<template>
  <section class="version-selector" aria-label="选择更新类型">
    <div class="version-selector-head">
      <span>当前版本</span>
      <strong>{{ current }}</strong>
    </div>
    <div class="version-bump-grid">
      <button
        v-for="option in options"
        :key="option.type"
        type="button"
        :class="['version-bump-option', selected === option.type && 'active']"
        @click="choose(option.type)"
      >
        <span>{{ option.title }}</span>
        <strong>{{ option.version }}</strong>
        <small>{{ option.detail }}</small>
      </button>
    </div>
    <label class="field-label compact">
      <span>版本号</span>
      <input :value="modelValue" maxlength="80" placeholder="例如 0.1.0" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    </label>
    <p v-if="invalid" class="field-hint danger">版本号必须使用 SemVer，例如 0.1.0、1.0.0-beta.1 或 1.0.0+build.5。</p>
  </section>
</template>
