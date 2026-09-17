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
  <Modal title="确认采集命令" description="系统规则提供回显结构；本次采集保存你填写的具体命令。" size="editor" motion="workflow" :open="true" @close="emit('close')">
    <div class="command-instance-form">
      <section v-if="props.expression" class="command-instance-source"><span>来源规则 · 只读</span><code>{{ props.expression }}</code></section>
      <label class="field-label"><span>具体采集命令</span><input v-model="command" aria-label="具体采集命令" :aria-invalid="Boolean(parsed.error || error)" aria-describedby="command-instance-help" placeholder="例如 show routes vrf &lt;vrf&gt; detail" /></label>
      <p id="command-instance-help" class="command-instance-help">只有本条命令的 &lt;参数&gt; 会生成输入；请确定实际使用的可选分支。</p>
      <section class="command-instance-parameters" aria-label="实例输入参数"><strong>实例参数 <span>{{ parsed.names.length }}</span></strong><div v-if="parsed.names.length"><code v-for="name in parsed.names" :key="name">{{ name }}</code></div><p v-else>无输入参数，将使用固定命令。</p></section>
      <p v-if="parsed.error || error" class="workflow-command-notice is-error" role="alert"><strong>无法预览</strong>{{ parsed.error || error }}</p>
      <p v-if="busy" class="workflow-command-notice is-info" role="status">正在检查命令并加载输出 Schema…</p>
      <template v-if="preview">
        <p v-for="warning in preview.warnings" :key="warning.code" class="workflow-command-notice" :class="warning.code === 'COMMAND_MATCH_DYNAMIC' ? 'is-info' : 'is-warning'" role="status"><strong>{{ warning.code === 'COMMAND_MATCH_DYNAMIC' ? '动态参数' : '匹配提醒' }}</strong>{{ warning.message }}</p>
        <details class="command-instance-schema"><summary>输出 Schema <span>来源只读</span></summary><pre>{{ JSON.stringify(preview.definition.outputs, null, 2) }}</pre></details>
      </template>
    </div>
    <footer class="modal-actions"><UiButton variant="secondary" @click="emit('close')">取消</UiButton><UiButton variant="primary" :disabled="!preview || busy" @click="preview && emit('confirm', preview.definition)">确认命令并添加</UiButton></footer>
  </Modal>
</template>
