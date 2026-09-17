<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { api } from "../../../lib/api";

const props = defineProps<{ sourceId: string; command: string }>();
const messages = ref<Array<{ text: string; kind: "info" | "warning" | "error" }>>([]);
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
      if (!request.signal.aborted) messages.value = result.warnings.map((item) => ({ text: item.message, kind: item.code === "COMMAND_MATCH_DYNAMIC" ? "info" : "warning" }));
    } catch (reason) {
      if (!request.signal.aborted) messages.value = [{ text: reason instanceof Error ? reason.message : "来源匹配检查失败。", kind: "error" }];
    }
  }, 300);
}, { immediate: true });
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort(); });
</script>

<template>
  <p v-for="message in messages" :key="message.text" :role="message.kind === 'error' ? 'alert' : 'status'" :class="['workflow-command-notice', `is-${message.kind}`]">
    <strong>{{ { info: '动态参数', warning: '匹配提醒', error: '检查失败' }[message.kind] }}</strong>{{ message.text }}
  </p>
</template>
