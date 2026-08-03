<script setup lang="ts">
import { Plus, Trash2 } from "lucide-vue-next";
import UiButton from "../../../../components/ui/UiButton.vue";
import UiIconButton from "../../../../components/ui/UiIconButton.vue";
import type { CollectionCall, CollectionDefinition, WorkflowDebugCollectionFixture, WorkflowDebugScalar } from "../../../../types";
import { cloneDebugValue, hasDebugValue } from "../form";
import WorkflowDebugScalarField from "./WorkflowDebugScalarField.vue";

const props = defineProps<{
  call: CollectionCall;
  definition?: CollectionDefinition;
  fixture?: WorkflowDebugCollectionFixture;
  disabled?: boolean;
}>();
const emit = defineEmits<{ change: [fixture: WorkflowDebugCollectionFixture | null] }>();

function setEnabled(enabled: boolean): void {
  emit("change", enabled ? { raw_output: [], outputs: {} } : null);
}

function changeRaw(index: number, value: string): void {
  const next = current();
  next.raw_output.splice(index, 1, value);
  emit("change", next);
}

function addRaw(): void {
  const next = current();
  next.raw_output.push("");
  emit("change", next);
}

function removeRaw(index: number): void {
  const next = current();
  next.raw_output.splice(index, 1);
  emit("change", next);
}

function setOutputPresence(id: string, present: boolean, initial: WorkflowDebugScalar): void {
  const next = current();
  if (present) next.outputs[id] = initial;
  else delete next.outputs[id];
  emit("change", next);
}

function setOutput(id: string, value: WorkflowDebugScalar): void {
  const next = current();
  next.outputs[id] = value;
  emit("change", next);
}

function current(): WorkflowDebugCollectionFixture {
  return cloneDebugValue(props.fixture ?? { raw_output: [], outputs: {} });
}
</script>

<template>
  <section class="workflow-debug-fixture">
    <header class="workflow-debug-fixture-head">
      <div><strong>{{ props.call.name || props.definition?.metadata.name || "未命名采集" }}</strong><small>{{ props.call.key || props.call.id }}</small></div>
      <label class="workflow-debug-presence"><input type="checkbox" :checked="Boolean(props.fixture)" :disabled="props.disabled" @change="setEnabled(($event.target as HTMLInputElement).checked)" />提供采集结果</label>
    </header>
    <div v-if="props.fixture" class="workflow-debug-fixture-body">
      <div class="workflow-debug-subhead"><div><strong>设备回显</strong><small>数组中每一项原样提交给执行器。</small></div><UiButton size="sm" :disabled="props.disabled" @click="addRaw"><template #icon><Plus /></template>添加回显</UiButton></div>
      <div v-if="props.fixture.raw_output.length" class="workflow-debug-output-lines">
        <div v-for="(line, index) in props.fixture.raw_output" :key="index" class="workflow-debug-output-line">
          <textarea rows="2" :value="line" :disabled="props.disabled" :aria-label="`第 ${index + 1} 条设备回显`" @input="changeRaw(index, ($event.target as HTMLTextAreaElement).value)" />
          <UiIconButton label="删除这条回显" variant="danger" size="sm" :disabled="props.disabled" @click="removeRaw(index)"><Trash2 /></UiIconButton>
        </div>
      </div>
      <p v-else class="workflow-debug-empty-inline">尚未添加设备回显。</p>
      <div v-if="props.definition?.outputs.length" class="workflow-debug-output-values">
        <div class="workflow-debug-subhead"><div><strong>结构化输出</strong><small>键使用写作侧 output ID，未勾选表示不提供。</small></div></div>
        <WorkflowDebugScalarField
          v-for="output in props.definition.outputs"
          :key="output.id"
          :label="output.schema.title || output.key"
          :description="output.schema.description"
          :schema="output.schema"
          :present="hasDebugValue(props.fixture.outputs, output.id)"
          :value="props.fixture.outputs[output.id]"
          :disabled="props.disabled"
          @presence="(present, initial) => setOutputPresence(output.id, present, initial)"
          @change="setOutput(output.id, $event)"
        />
      </div>
      <p v-else-if="!props.definition" class="form-error">当前保存版本中找不到该采集定义，无法配置结构化输出。</p>
    </div>
  </section>
</template>
