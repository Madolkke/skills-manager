<script setup lang="ts">
import { FileArchive, FolderOpen } from "lucide-vue-next";
import { ref } from "vue";

const emit = defineEmits<{ files: [folderFiles: File[], zipFile: File | null] }>();

const folderRef = ref<HTMLInputElement | null>(null);
const zipRef = ref<HTMLInputElement | null>(null);
const label = ref("尚未选择 bundle");

function acceptFolder(files: FileList | null): void {
  const folderFiles = files ? Array.from(files) : [];
  const root = (folderFiles[0] as (File & { webkitRelativePath?: string }) | undefined)?.webkitRelativePath?.split("/")[0] ?? "bundle";
  label.value = folderFiles.length ? `${root} · ${folderFiles.length} files` : "尚未选择 bundle";
  emit("files", folderFiles, null);
}

function acceptZip(files: FileList | null): void {
  const zip = files?.[0] ?? null;
  label.value = zip ? `${zip.name} · zip` : "尚未选择 bundle";
  emit("files", [], zip);
}
</script>

<template>
  <div class="bundle-picker">
    <input
      ref="folderRef"
      name="folder_files"
      type="file"
      multiple
      class="hidden-input"
      webkitdirectory
      directory
      @change="acceptFolder(($event.target as HTMLInputElement).files)"
    />
    <input
      ref="zipRef"
      name="zip_file"
      type="file"
      accept=".zip"
      class="hidden-input"
      @change="acceptZip(($event.target as HTMLInputElement).files)"
    />
    <button class="picker-tile" type="button" @click="folderRef?.click()">
      <FolderOpen :size="24" />
      <span>选择文件夹</span>
    </button>
    <button class="picker-tile" type="button" @click="zipRef?.click()">
      <FileArchive :size="24" />
      <span>上传 zip</span>
    </button>
    <div class="picker-label">{{ label }}</div>
  </div>
</template>
