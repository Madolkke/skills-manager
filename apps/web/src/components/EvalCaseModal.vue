<script setup lang="ts">
import { ref } from "vue";
import type { EvalSetCase } from "../types";
import Modal from "./Modal.vue";

export type EvalCaseFormData = {
  title: string;
  input_text: string;
  expected_output: string;
  attachment_name?: string;
  attachment_base64?: string;
  notes: string;
};

const props = defineProps<{ caseItem?: EvalSetCase | null; busy: boolean }>();
const emit = defineEmits<{ close: []; submit: [data: EvalCaseFormData] }>();

const form = ref<EvalCaseFormData>({
  title: props.caseItem?.case.title ?? "",
  input_text: props.caseItem?.case_version.input_artifact.content_text ?? "",
  expected_output: props.caseItem?.case_version.expected_output_artifact.content_text ?? "",
  attachment_name: undefined,
  attachment_base64: undefined,
  notes: props.caseItem?.case_version.notes ?? "",
});
const editing = Boolean(props.caseItem);
const attachmentLabel = ref(props.caseItem?.case_version.attachment_artifact ? artifactFileName(props.caseItem.case_version.attachment_artifact.locator) : "未选择压缩包");

async function acceptZip(files: FileList | null): Promise<void> {
  const file = files?.[0] ?? null;
  if (!file) {
    form.value.attachment_name = undefined;
    form.value.attachment_base64 = undefined;
    attachmentLabel.value = props.caseItem?.case_version.attachment_artifact ? artifactFileName(props.caseItem.case_version.attachment_artifact.locator) : "未选择压缩包";
    return;
  }
  form.value.attachment_name = file.name;
  form.value.attachment_base64 = await fileToBase64(file);
  attachmentLabel.value = `${file.name} · ${formatBytes(file.size)}`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("读取压缩包失败。"));
    reader.readAsDataURL(file);
  });
}

function artifactFileName(locator: string): string {
  return locator.split(":").at(-1) || "case-attachment.zip";
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
</script>

<template>
  <Modal :title="editing ? '编辑 case' : '添加 case'" description="保存后会形成 case version，并更新当前测评集。" @close="emit('close')">
    <form
      class="form-stack"
      @submit.prevent="emit('submit', form)"
    >
      <label class="field-label">
        标题
        <input v-model="form.title" placeholder="PR: missing owner filter" required>
      </label>
      <label class="field-label">
        Input
        <textarea v-model="form.input_text" placeholder="代码 diff、用户请求、上下文" required />
      </label>
      <label class="field-label">
        Expected output
        <textarea v-model="form.expected_output" placeholder="应该指出什么" required />
      </label>
      <label class="field-label">
        附件压缩包
        <input type="file" accept=".zip,application/zip" @change="acceptZip(($event.target as HTMLInputElement).files)">
        <span class="field-help">{{ attachmentLabel }}</span>
      </label>
      <label class="field-label">
        Notes
        <input v-model="form.notes" placeholder="来源或维护说明，可选">
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="submit" :disabled="busy">
          {{ busy ? "保存中..." : editing ? "保存 case version" : "添加 case" }}
        </button>
      </div>
    </form>
  </Modal>
</template>
