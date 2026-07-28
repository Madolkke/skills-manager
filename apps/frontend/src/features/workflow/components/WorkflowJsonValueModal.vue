<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowJsonSchema } from "../../../types";
import { workflowValueMatchesSchema } from "../workflowJsonSchema";

const props = defineProps<{ open: boolean; value: unknown; schema: WorkflowJsonSchema; fieldName: string; readonly: boolean }>();
const emit = defineEmits<{ close: []; confirm: [value: unknown] }>();
const source = ref("");
const parsed = computed(() => {
  try { return { validJson: true, value: JSON.parse(source.value) as unknown }; }
  catch { return { validJson: false, value: undefined }; }
});
const schemaMatch = computed(() => parsed.value.validJson && workflowValueMatchesSchema(parsed.value.value, props.schema));

watch(() => props.open, (open) => {
  if (open) source.value = JSON.stringify(props.value ?? (props.schema.type === "array" ? [] : {}), null, 2);
}, { immediate: true });

function confirm(): void {
  if (parsed.value.validJson) emit("confirm", parsed.value.value);
}
</script>

<template>
  <Modal :open="props.open" size="wide" motion="workflow" :title="`编辑固定值 · ${props.fieldName}`" description="填写合法 JSON；与 Schema 不匹配时保留值并给出警告。" @close="emit('close')">
    <div class="workflow-json-value-body"><textarea v-model="source" rows="18" spellcheck="false" :disabled="props.readonly" aria-label="JSON 固定值" /><p v-if="!parsed.validJson" class="field-error">请输入合法 JSON。</p><p v-else-if="!schemaMatch" class="workflow-field-warning">当前 JSON 与字段 Schema 不匹配，仍可保存为草稿。</p></div>
    <footer class="modal-actions"><UiButton variant="secondary" @click="emit('close')">取消</UiButton><UiButton :disabled="props.readonly || !parsed.validJson" @click="confirm">确认固定值</UiButton></footer>
  </Modal>
</template>
