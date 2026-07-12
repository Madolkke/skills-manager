<script setup lang="ts">
import { AlertTriangle } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";

const props = withDefaults(defineProps<{
  title: string;
  description: string;
  open?: boolean;
  confirmLabel?: string;
  tone?: "danger" | "warning";
}>(), { confirmLabel: "确认", tone: "warning", open: true });
const emit = defineEmits<{ close: []; confirm: []; closed: [] }>();
</script>

<template>
  <Modal :title="props.title" :open="props.open" motion="workflow" @close="emit('close')" @after-leave="emit('closed')">
    <div class="workflow-confirm-content">
      <div :class="['workflow-confirm-icon', props.tone]"><AlertTriangle :size="22" /></div>
      <p>{{ props.description }}</p>
      <div class="modal-actions">
        <UiButton variant="secondary" size="lg" @click="emit('close')">取消</UiButton>
        <UiButton :variant="props.tone === 'danger' ? 'danger' : 'primary'" size="lg" @click="emit('confirm')">{{ props.confirmLabel }}</UiButton>
      </div>
    </div>
  </Modal>
</template>
