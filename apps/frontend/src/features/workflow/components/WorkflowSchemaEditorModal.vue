<script setup lang="ts">
import { Check, Clipboard, Code2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowJsonSchema } from "../../../types";
import { canonicalWorkflowSchema, validWorkflowSchema } from "../workflowJsonSchema";
import { cloneWorkflow } from "../domain/utils";
import WorkflowSchemaNodeEditor from "./WorkflowSchemaNodeEditor.vue";

const props = defineProps<{ open: boolean; schema: WorkflowJsonSchema; fieldKey: string; readonly: boolean }>();
const emit = defineEmits<{ close: []; confirm: [schema: WorkflowJsonSchema] }>();
const draft = ref<WorkflowJsonSchema>(cloneWorkflow(props.schema));
const previewOpen = ref(false);
const copied = ref(false);
const valid = computed(() => validWorkflowSchema(draft.value));
const preview = computed(() => JSON.stringify(canonicalWorkflowSchema(draft.value), null, 2));

watch(() => props.open, (open) => {
  if (!open) return;
  draft.value = cloneWorkflow(props.schema);
  previewOpen.value = false;
  copied.value = false;
});

async function copyPreview(): Promise<void> {
  await navigator.clipboard.writeText(preview.value);
  copied.value = true;
  window.setTimeout(() => { copied.value = false; }, 1000);
}

function confirm(): void {
  if (!valid.value) return;
  emit("confirm", canonicalWorkflowSchema(draft.value));
}
</script>

<template>
  <Modal :open="props.open" size="wide" motion="workflow" :title="`编辑 Schema · ${props.fieldKey || '未命名字段'}`" description="定义字段自身以及递归对象或数组结构。" @close="emit('close')">
    <div class="workflow-schema-modal-body">
      <WorkflowSchemaNodeEditor :schema="draft" :readonly="props.readonly" @change="draft = $event" />
      <section class="workflow-schema-preview">
        <button type="button" @click="previewOpen = !previewOpen"><Code2 :size="15" />JSON Schema 预览 <small>{{ previewOpen ? "收起" : "展开" }}</small></button>
        <div v-if="previewOpen"><pre>{{ preview }}</pre><UiButton size="sm" variant="secondary" @click="copyPreview"><template #icon><Check v-if="copied" /><Clipboard v-else /></template>{{ copied ? "已复制" : "复制" }}</UiButton></div>
      </section>
      <p v-if="!valid" class="field-error">Schema 不合法：对象属性 Key 必须唯一且非空，required 必须引用已有属性。</p>
    </div>
    <footer class="modal-actions"><UiButton variant="secondary" @click="emit('close')">取消</UiButton><UiButton :disabled="props.readonly || !valid" @click="confirm">确认 Schema</UiButton></footer>
  </Modal>
</template>
