<script setup lang="ts">
import Modal from "../../../components/Modal.vue";
import type { EvalSetCase } from "../../../types";
import type { EvalCaseFormData } from "../lib/evalCaseForm";
import EvalCaseEditor from "./EvalCaseEditor.vue";

export type { EvalCaseFormData, StepValidation } from "../lib/evalCaseForm";

const props = defineProps<{ caseItem?: EvalSetCase | null; busy: boolean }>();
const emit = defineEmits<{ close: []; submit: [data: EvalCaseFormData] }>();
const editing = Boolean(props.caseItem);
</script>

<template>
  <Modal :title="editing ? '编辑测试场景' : '添加测试场景'" description="先写一个输入和判断条件，就可以运行一个最小测试场景。" size="wide" @close="emit('close')">
    <EvalCaseEditor :case-item="caseItem" :busy="busy" @cancel="emit('close')" @submit="emit('submit', $event)" />
  </Modal>
</template>
