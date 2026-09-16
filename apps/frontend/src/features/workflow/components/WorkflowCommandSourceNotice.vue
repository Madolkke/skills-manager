<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { api } from "../../../lib/api";

const props = defineProps<{ sourceId: string; command: string }>();
const messages = ref<string[]>([]);
let timer: ReturnType<typeof setTimeout> | undefined;
let controller: AbortController | undefined;

/** 编辑后重新读取来源匹配提醒，不保存或覆盖草稿。 */
watch(() => [props.sourceId, props.command], () => {
  clearTimeout(timer);
  controller?.abort();
  messages.value = [];
  timer = setTimeout(async () => {
    const request = new AbortController();
    controller = request;
    try {
      const result = await api.previewCommandInstance(props.sourceId, props.command, request.signal);
      if (!request.signal.aborted) messages.value = result.warnings.map((item) => item.message);
    } catch (reason) {
      if (!request.signal.aborted) messages.value = [reason instanceof Error ? reason.message : "来源匹配检查失败。"];
    }
  }, 300);
}, { immediate: true });
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); });
</script>

<template><p v-for="message in messages" :key="message" role="status" class="workflow-command-notice">{{ message }}</p></template>
<style scoped>.workflow-command-notice { overflow-wrap: anywhere; }</style>
