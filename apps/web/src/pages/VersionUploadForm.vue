<script setup lang="ts">
import { computed, ref } from "vue";
import BundlePicker from "../components/BundlePicker.vue";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";
import type { SkillDetail } from "../types";

const props = withDefaults(defineProps<{ skill: SkillDetail; actionsClassName?: string }>(), { actionsClassName: "modal-actions" });
const emit = defineEmits<{ cancel: []; uploaded: [] }>();

const folderFiles = ref<File[]>([]);
const zipFile = ref<File | null>(null);
const displayName = ref("");
const busy = ref(false);
const error = ref<string | null>(null);
const canSubmit = computed(() => !busy.value && Boolean(zipFile.value || folderFiles.value.length));

async function submit(): Promise<void> {
  busy.value = true;
  error.value = null;
  try {
    const source = await sourceFromFiles(folderFiles.value, zipFile.value);
    await api.createSkillVersion({ skill_id: props.skill.skill.id, source, make_current: true, display_name: cleanName(displayName.value) });
    emit("uploaded");
  } catch (caught) {
    error.value = caught instanceof ApiError || caught instanceof Error ? caught.message : "上传失败。";
  } finally {
    busy.value = false;
  }
}

function cleanName(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}
</script>

<template>
  <div class="form-stack">
    <div v-if="error" class="form-error">{{ error }}</div>
    <div class="hint-strip">将追加新的 SkillVersion，并设置为当前版本。</div>
    <label class="field-label">
      <span>版本名称</span>
      <input v-model="displayName" maxlength="80" :placeholder="`例如 ${skill.skill.slug} stable`" />
    </label>
    <BundlePicker
      @files="
        (nextFolderFiles, nextZipFile) => {
          folderFiles = nextFolderFiles;
          zipFile = nextZipFile;
        }
      "
    />
    <div :class="actionsClassName">
      <button class="secondary-button" type="button" @click="emit('cancel')">取消</button>
      <button class="primary-button" type="button" :disabled="!canSubmit" @click="submit">
        {{ busy ? "上传中..." : "确认上传" }}
      </button>
    </div>
  </div>
</template>
