<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import Modal from "../../../components/Modal.vue";
import UiButton from "../../../components/ui/UiButton.vue";
import { api } from "../../../lib/api";
import type { CollectionDefinition } from "../../../types";
import { parseCliCommandParameters } from "../domain/cliCommandParameters";

const props = defineProps<{ commandId: string; expression?: string; initialCommand?: string }>();
const emit = defineEmits<{ close: []; confirm: [definition: CollectionDefinition] }>();
const command = ref(props.initialCommand ?? "");
const parsed = computed(() => parseCliCommandParameters(command.value));
const preview = ref<Awaited<ReturnType<typeof api.previewCommandInstance>>>();
const busy = ref(false);
const error = ref("");
let controller: AbortController | undefined;
let timer: ReturnType<typeof setTimeout> | undefined;

/** 草稿变化立即废弃旧预览，防止快速输入后提交过期命令。 */
watch(command, () => {
  controller?.abort();
  clearTimeout(timer);
  preview.value = undefined;
  error.value = "";
  busy.value = false;
  if (!command.value.trim() || parsed.value.error) return;
  busy.value = true;
  timer = setTimeout(async () => {
    const request = new AbortController();
    controller = request;
    try {
      const result = await api.previewCommandInstance(props.commandId, command.value, request.signal);
      if (!request.signal.aborted) preview.value = result;
    } catch (reason) {
      if (!request.signal.aborted) error.value = reason instanceof Error ? reason.message : "预览失败，请重试。";
    } finally {
      if (!request.signal.aborted) busy.value = false;
    }
  }, 250);
}, { immediate: true });
onBeforeUnmount(() => { controller?.abort(); clearTimeout(timer); });
</script>

<template>
  <Modal title="确认采集命令" :open="true" @close="emit('close')">
    <div class="command-instance-form">
      <p v-if="props.expression">来源表达式：<code>{{ props.expression }}</code></p>
      <label class="field-label"><span>具体采集命令</span><input v-model="command" aria-label="具体采集命令" placeholder="例如 show routes vrf <vrf> detail" /></label>
      <p>只有本条命令的 &lt;参数&gt; 会生成输入；请确定实际使用的可选分支。</p>
      <p>输入参数：{{ parsed.names.join('、') || '无' }}</p>
      <p v-if="parsed.error || error" role="alert">{{ parsed.error || error }}</p>
      <p v-if="busy" role="status">正在预览…</p>
      <template v-if="preview">
        <p v-for="warning in preview.warnings" :key="warning.code" role="status">{{ warning.message }}</p>
        <details><summary>回显 Schema（来源只读）</summary><pre>{{ JSON.stringify(preview.definition.outputs, null, 2) }}</pre></details>
      </template>
      <div class="modal-actions"><UiButton variant="secondary" @click="emit('close')">取消</UiButton><UiButton :disabled="!preview || busy" @click="preview && emit('confirm', preview.definition)">确认命令并添加</UiButton></div>
    </div>
  </Modal>
</template>

<style scoped>
.command-instance-form { display: grid; gap: 12px; min-width: 0; }
.command-instance-form input { width: 100%; min-width: 0; }
.command-instance-form p { overflow-wrap: anywhere; }
.command-instance-form pre { max-height: 280px; overflow: auto; }
.modal-actions { flex-wrap: wrap; }
</style>
