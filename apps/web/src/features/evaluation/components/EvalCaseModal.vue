<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../../lib/api";
import { promptTemplateLabel } from "../lib/evalRunner";
import type { EvalPromptTemplate, EvalSetCase } from "../../../types";
import Modal from "../../../components/Modal.vue";

export type EvalCaseFormData = {
  title: string;
  input_text: string;
  expected_output: string;
  attachment_name?: string;
  attachment_base64?: string;
  prompt_template_id: string;
  prompt_text: string;
  model_provider_id?: string | null;
  model_id?: string | null;
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
  prompt_template_id: props.caseItem?.case_version.prompt_template_id ?? "standard_pass_fail",
  prompt_text: props.caseItem?.case_version.prompt_text ?? "",
  model_provider_id: props.caseItem?.case_version.model_provider_id ?? null,
  model_id: props.caseItem?.case_version.model_id ?? null,
  notes: props.caseItem?.case_version.notes ?? "",
});
const editing = Boolean(props.caseItem);
const attachmentLabel = ref(props.caseItem?.case_version.attachment_artifact ? artifactFileName(props.caseItem.case_version.attachment_artifact.locator) : "未选择压缩包");
const templates = ref<EvalPromptTemplate[]>([]);

onMounted(async () => {
  templates.value = await api.listEvalPromptTemplates();
});

function updateProvider(value: string): void {
  form.value.model_provider_id = value || null;
  if (!value) form.value.model_id = null;
  if (value && !form.value.model_id) form.value.model_id = "deepseek-v4-flash";
}

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
  <Modal :title="editing ? '编辑测试例' : '添加测试例'" description="保存后会形成测试例版本，并更新当前测评集。" @close="emit('close')">
    <form
      class="form-stack"
      @submit.prevent="emit('submit', form)"
    >
      <label class="field-label">
        标题
        <input v-model="form.title" placeholder="例如：缺少负责人过滤条件" required>
      </label>
      <label class="field-label">
        测试输入
        <textarea v-model="form.input_text" placeholder="代码 diff、用户请求、上下文" required />
      </label>
      <label class="field-label">
        预期结果
        <textarea v-model="form.expected_output" placeholder="应该指出什么" required />
      </label>
      <label class="field-label">
        附件压缩包
        <input type="file" accept=".zip,application/zip" @change="acceptZip(($event.target as HTMLInputElement).files)">
        <span class="field-help">{{ attachmentLabel }}；运行时会解压复制到工作目录。</span>
      </label>
      <div class="runner-config-grid">
        <label class="field-label">
          提示词模板
          <select v-model="form.prompt_template_id">
            <option v-for="template in templates" :key="template.id" :value="template.id">{{ promptTemplateLabel(template.id) }}</option>
          </select>
        </label>
        <label class="field-label">
          服务商
          <select :value="form.model_provider_id ?? ''" @change="updateProvider(($event.target as HTMLSelectElement).value)">
            <option value="">使用 Opencode 默认模型</option>
            <option value="deepseek">DeepSeek</option>
          </select>
        </label>
        <label class="field-label">
          模型
          <select v-model="form.model_id" :disabled="!form.model_provider_id">
            <option :value="null">使用默认模型</option>
            <option value="deepseek-v4-flash">deepseek-v4-flash</option>
            <option value="deepseek-v4-pro">deepseek-v4-pro</option>
          </select>
        </label>
      </div>
      <label class="field-label">
        自定义提示词
        <textarea v-model="form.prompt_text" placeholder="留空则使用模板。可使用 {skill_dir}、{workdir}、{input}、{expected_output}、{result_json_path}" />
      </label>
      <label class="field-label">
        备注
        <input v-model="form.notes" placeholder="来源或维护说明，可选">
      </label>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="submit" :disabled="busy">
          {{ busy ? "保存中..." : editing ? "保存测试例版本" : "添加测试例" }}
        </button>
      </div>
    </form>
  </Modal>
</template>
