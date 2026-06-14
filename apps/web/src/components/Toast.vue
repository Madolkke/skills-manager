<script setup lang="ts">
import { CheckCircle2, Info, XCircle } from "lucide-vue-next";
import { computed, onBeforeUnmount, watch } from "vue";
import type { ToastState } from "../types";

const props = defineProps<{ toast: ToastState }>();
const emit = defineEmits<{ close: [] }>();

let timer: number | null = null;
const icon = computed(() => (props.toast?.tone === "success" ? CheckCircle2 : props.toast?.tone === "danger" ? XCircle : Info));

watch(
  () => props.toast,
  (toast) => {
    clearTimer();
    if (toast) timer = window.setTimeout(() => emit("close"), 4200);
  },
  { immediate: true },
);

onBeforeUnmount(clearTimer);

function clearTimer(): void {
  if (timer === null) return;
  window.clearTimeout(timer);
  timer = null;
}
</script>

<template>
  <div v-if="toast" :class="['toast', toast.tone]" role="status">
    <component :is="icon" :size="20" />
    <span>{{ toast.message }}</span>
    <button type="button" aria-label="关闭通知" @click="emit('close')">关闭</button>
  </div>
</template>
