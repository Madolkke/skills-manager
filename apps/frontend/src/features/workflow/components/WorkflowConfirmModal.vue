<script setup lang="ts">
import { AlertTriangle } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";

const props = withDefaults(defineProps<{
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "danger" | "warning";
}>(), { confirmLabel: "确认", tone: "warning" });
const emit = defineEmits<{ close: []; confirm: [] }>();
</script>

<template>
  <Modal :title="props.title" @close="emit('close')">
    <div class="workflow-confirm-content">
      <div :class="['workflow-confirm-icon', props.tone]"><AlertTriangle :size="22" /></div>
      <p>{{ props.description }}</p>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button :class="props.tone === 'danger' ? 'danger-button' : 'primary-button'" type="button" @click="emit('confirm')">{{ props.confirmLabel }}</button>
      </div>
    </div>
  </Modal>
</template>
