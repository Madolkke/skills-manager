<script setup lang="ts">
import { ref } from "vue";
import type { EvalSetCase } from "../types";
import Modal from "./Modal.vue";

export type EvalCaseFormData = {
  title: string;
  input_text: string;
  expected_output: string;
  notes: string;
};

const props = defineProps<{ caseItem?: EvalSetCase | null; busy: boolean }>();
const emit = defineEmits<{ close: []; submit: [data: EvalCaseFormData] }>();

const form = ref<EvalCaseFormData>({
  title: props.caseItem?.case.title ?? "",
  input_text: props.caseItem?.case_version.input_artifact.content_text ?? "",
  expected_output: props.caseItem?.case_version.expected_output_artifact.content_text ?? "",
  notes: props.caseItem?.case_version.notes ?? "",
});
const editing = Boolean(props.caseItem);
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
