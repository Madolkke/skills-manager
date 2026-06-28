<script setup lang="ts">
import { FileCog, UploadCloud } from "lucide-vue-next";

defineProps<{ title: string; workspaceLabel: string; showValidation?: boolean }>();
const emit = defineEmits<{ "update:title": [value: string]; configureWorkspace: []; zip: [files: FileList | null] }>();
</script>

<template>
  <section class="scenario-basics">
    <label class="field-label scenario-title-field">
      测试场景标题
      <input :value="title" placeholder="例如：生成项目说明文件" required @input="emit('update:title', ($event.target as HTMLInputElement).value)">
      <span v-if="showValidation && !title.trim()" class="field-hint danger">填写测试场景标题。</span>
    </label>
    <div class="scenario-workspace-card">
      <button class="scenario-workspace-config" type="button" @click="emit('configureWorkspace')">
        <span class="scenario-upload-icon"><FileCog :size="20" /></span>
        <span>
          <strong>布置工作区</strong>
          <small>{{ workspaceLabel }}</small>
        </span>
        <em>运行时会解压为 Agent 的工作目录</em>
      </button>
      <label class="secondary-button scenario-zip-button">
        <UploadCloud :size="16" />
        上传 zip 替换
        <input type="file" accept=".zip,application/zip" @change="emit('zip', ($event.target as HTMLInputElement).files)">
      </label>
    </div>
  </section>
</template>
