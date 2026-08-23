<script setup lang="ts">
import { Check, ChevronDown, Clipboard, Code2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowJsonSchema } from "../../../types";
import { canonicalWorkflowSchema, validWorkflowSchema, type WorkflowSchemaType } from "../workflowJsonSchema";
import { cloneWorkflow } from "../domain/utils";
import WorkflowSchemaNodeEditor from "./WorkflowSchemaNodeEditor.vue";

const props = defineProps<{ open: boolean; schema: WorkflowJsonSchema; fieldKey: string; readonly: boolean; rootObjectOnly?: boolean; identifierOnly?: boolean }>();
const emit = defineEmits<{ close: []; confirm: [schema: WorkflowJsonSchema] }>();
const draft = ref<WorkflowJsonSchema>(cloneWorkflow(props.schema));
const previewOpen = ref(false);
const copied = ref(false);
const complexSchemaTypes: WorkflowSchemaType[] = ["object", "array"];
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
  <Modal :open="props.open" size="editor" motion="workflow" :title="`编辑 Schema · ${props.fieldKey || '未命名字段'}`" description="配置对象或数组的递归结构；字段名称和说明在列表中编辑。" @close="emit('close')">
    <div class="workflow-schema-modal-body">
      <WorkflowSchemaNodeEditor :schema="draft" :readonly="props.readonly" :allowed-types="props.rootObjectOnly ? ['object'] : complexSchemaTypes" :identifier-only="props.identifierOnly" :show-metadata="false" @change="draft = $event" />
      <section class="workflow-schema-preview">
        <button type="button" :aria-expanded="previewOpen" aria-controls="workflow-schema-preview-json" @click="previewOpen = !previewOpen"><Code2 :size="16" /><span>JSON Schema 预览</span><ChevronDown :class="previewOpen && 'open'" :size="17" /></button>
        <div v-if="previewOpen" id="workflow-schema-preview-json"><pre>{{ preview }}</pre><UiButton size="sm" variant="secondary" @click="copyPreview"><template #icon><Check v-if="copied" /><Clipboard v-else /></template>{{ copied ? "已复制" : "复制" }}</UiButton></div>
      </section>
      <p v-if="!valid" class="field-error">Schema 不合法：对象属性 Key 必须唯一且非空，required 必须引用已有属性。</p>
    </div>
    <footer class="modal-actions"><UiButton variant="secondary" @click="emit('close')">取消</UiButton><UiButton variant="primary" :disabled="props.readonly || !valid" @click="confirm">确认 Schema</UiButton></footer>
  </Modal>
</template>
