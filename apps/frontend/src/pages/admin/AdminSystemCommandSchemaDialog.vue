<script setup lang="ts">
import { Braces } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import Modal from "../../components/Modal.vue";
import UiButton from "../../components/ui/UiButton.vue";
import type { WorkflowJsonSchema } from "../../types";

const props = defineProps<{
  open: boolean;
  schema: WorkflowJsonSchema;
  normalize: (value: unknown) => WorkflowJsonSchema;
  validate: (value: unknown) => string[];
  title?: string;
  description?: string;
}>();
const emit = defineEmits<{ close: []; confirm: [schema: WorkflowJsonSchema] }>();

const text = ref("");
const error = ref("");
const parsed = ref<WorkflowJsonSchema | null>(null);
const canConfirm = computed(() => Boolean(parsed.value) && !error.value);

watch(() => [props.open, props.schema] as const, ([open, schema]) => {
  if (!open) return;
  text.value = JSON.stringify(schema, null, 2);
  error.value = "";
  parsed.value = schema;
}, { immediate: true });

function parse(value: string): void {
  text.value = value;
  try {
    const candidate = JSON.parse(value) as unknown;
    const errors = props.validate(candidate);
    if (errors.length) {
      error.value = errors[0]!;
      parsed.value = null;
      return;
    }
    parsed.value = props.normalize(candidate);
    error.value = "";
  } catch {
    error.value = "输出 Schema JSON 格式不正确。";
    parsed.value = null;
  }
}

function format(): void {
  if (!parsed.value) return;
  text.value = JSON.stringify(parsed.value, null, 2);
}

function confirm(): void {
  if (!parsed.value || error.value) return;
  emit("confirm", parsed.value);
}
</script>

<template>
  <Modal :title="props.title || '编辑原始 JSON Schema'" :description="props.description || '直接编辑完整 Schema；确认前会复用系统命令库的结构校验。'" size="editor" :open="props.open" @close="emit('close')">
    <div class="admin-command-schema-dialog-body">
      <textarea :value="text" class="admin-command-json admin-command-json-dialog" spellcheck="false" aria-label="原始 JSON Schema" @input="parse(($event.target as HTMLTextAreaElement).value)" />
      <div class="admin-command-json-foot">
        <span :class="error && 'has-error'">{{ error || "Schema 将按当前字段规则校验。" }}</span>
        <UiButton size="sm" variant="secondary" :disabled="Boolean(error)" @click="format"><template #icon><Braces /></template>格式化</UiButton>
      </div>
    </div>
    <div class="modal-actions">
      <UiButton variant="secondary" @click="emit('close')">取消</UiButton>
      <UiButton variant="primary" :disabled="!canConfirm" @click="confirm">确认 Schema</UiButton>
    </div>
  </Modal>
</template>
