<script setup lang="ts">
import { ref } from "vue";
import BundlePicker from "../components/BundlePicker.vue";
import Modal from "../components/Modal.vue";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";

const props = defineProps<{ actor: string }>();
const emit = defineEmits<{ close: []; created: [skillId: string] }>();

const folderFiles = ref<File[]>([]);
const zipFile = ref<File | null>(null);
const displayName = ref("");
const busy = ref(false);
const error = ref<string | null>(null);

async function submit(): Promise<void> {
  busy.value = true;
  error.value = null;
  try {
    const source = await sourceFromFiles(folderFiles.value, zipFile.value);
    const created = await api.importSkill({ owner_ref: props.actor, source, display_name: cleanName(displayName.value) });
    emit("created", created.skill_id);
  } catch (caught) {
    error.value = caught instanceof ApiError || caught instanceof Error ? caught.message : "创建失败。";
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
  <Modal title="新建 Skill" description="上传标准 Skill bundle，名称和说明会从 SKILL.md frontmatter 读取。" @close="emit('close')">
    <div class="form-stack">
      <div v-if="error" class="form-error">{{ error }}</div>
      <label class="field-label">
        <span>初始版本名称</span>
        <input v-model="displayName" maxlength="80" placeholder="例如 first usable build" />
      </label>
      <BundlePicker
        @files="
          (nextFolderFiles, nextZipFile) => {
            folderFiles = nextFolderFiles;
            zipFile = nextZipFile;
          }
        "
      />
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" :disabled="busy || (!zipFile && folderFiles.length === 0)" @click="submit">
          {{ busy ? "创建中..." : "创建 Skill" }}
        </button>
      </div>
    </div>
  </Modal>
</template>
