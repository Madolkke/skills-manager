<script setup lang="ts">
import { AlertTriangle, RefreshCw } from "lucide-vue-next";

defineProps<{
  message: string;
  retryable?: boolean;
}>();

const emit = defineEmits<{
  retry: [];
}>();
</script>

<template>
  <section class="builder-load-alert" role="alert">
    <AlertTriangle :size="20" />
    <div>
      <strong>AI 创建暂不可用</strong>
      <p>{{ message }}</p>
    </div>
    <button v-if="retryable" class="secondary-button" type="button" @click="emit('retry')">
      <RefreshCw :size="16" />
      重试加载
    </button>
  </section>
</template>
