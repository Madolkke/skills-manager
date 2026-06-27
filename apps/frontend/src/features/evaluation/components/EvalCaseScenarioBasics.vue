<script setup lang="ts">
import { UploadCloud } from "lucide-vue-next";

defineProps<{ title: string; workspaceLabel: string; showValidation?: boolean }>();
const emit = defineEmits<{ "update:title": [value: string]; zip: [files: FileList | null] }>();
</script>

<template>
  <section class="scenario-basics">
    <label class="field-label scenario-title-field">
      测试场景标题
      <input :value="title" placeholder="例如：生成项目说明文件" required @input="emit('update:title', ($event.target as HTMLInputElement).value)">
      <span v-if="showValidation && !title.trim()" class="field-hint danger">填写测试场景标题。</span>
    </label>
    <label class="scenario-upload-card">
      <input type="file" accept=".zip,application/zip" @change="emit('zip', ($event.target as HTMLInputElement).files)">
      <span class="scenario-upload-icon"><UploadCloud :size="20" /></span>
      <span>
        <strong>工作目录压缩包</strong>
        <small>{{ workspaceLabel }}</small>
      </span>
      <em>运行时会解压为 Agent 的工作目录</em>
    </label>
  </section>
</template>
