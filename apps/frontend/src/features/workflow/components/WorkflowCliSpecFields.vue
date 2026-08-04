<script setup lang="ts">
import { CirclePlus, Trash2 } from "lucide-vue-next";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CliCollectionSpec, CollectionDefinition } from "../../../types";
import { createWorkflowId } from "../domain/utils";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean }>();
const emit = defineEmits<{ change: [spec: CliCollectionSpec] }>();

function update(recipe: (spec: CliCollectionSpec) => void): void {
  const spec: CliCollectionSpec = {
    collectionType: "cli",
    commandTemplate: props.definition.spec.collectionType === "cli" ? props.definition.spec.commandTemplate : "",
    outputSamples: props.definition.spec.collectionType === "cli" ? props.definition.spec.outputSamples : [],
  };
  recipe(spec);
  emit("change", spec);
}

function addSample(): void {
  update((spec) => spec.outputSamples.push({ id: createWorkflowId("sample"), name: `示例 ${spec.outputSamples.length + 1}`, stdout: "", inputValues: {} }));
}
</script>

<template>
  <section class="workflow-field-section" :class="props.definition.spec.collectionType === 'cli' && !props.definition.spec.commandTemplate.trim() && 'field-invalid'">
    <div class="workflow-subhead"><div><h3>采集命令</h3><p>CLI 命令模板，可引用定义中的输入参数。</p></div></div>
    <input
      class="workflow-code-input workflow-command-input"
      type="text"
      spellcheck="false"
      :value="props.definition.spec.collectionType === 'cli' ? props.definition.spec.commandTemplate : ''"
      :disabled="props.readonly"
      @input="update((spec) => { spec.commandTemplate = ($event.target as HTMLInputElement).value; })"
    />
  </section>

  <section class="workflow-field-section">
    <div class="workflow-subhead"><div><h3>回显示例</h3><p>{{ props.definition.spec.collectionType === 'cli' ? props.definition.spec.outputSamples.length : 0 }} 个样例</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addSample"><template #icon><CirclePlus /></template>添加</UiButton></div>
    <template v-if="props.definition.spec.collectionType === 'cli'">
      <article v-for="sample in props.definition.spec.outputSamples" :key="sample.id" class="workflow-sample">
        <div><input :value="sample.name" aria-label="样例名称" :disabled="props.readonly" @input="update((spec) => { const target = spec.outputSamples.find((item) => item.id === sample.id); if (target) target.name = ($event.target as HTMLInputElement).value; })" /><UiIconButton label="删除样例" size="sm" variant="danger" :disabled="props.readonly" @click="update((spec) => { spec.outputSamples = spec.outputSamples.filter((item) => item.id !== sample.id); })"><Trash2 /></UiIconButton></div>
        <textarea class="workflow-sample-output" rows="5" spellcheck="false" :value="sample.stdout" :disabled="props.readonly" @input="update((spec) => { const target = spec.outputSamples.find((item) => item.id === sample.id); if (target) target.stdout = ($event.target as HTMLTextAreaElement).value; })" />
      </article>
    </template>
    <p v-if="props.definition.spec.collectionType !== 'cli' || props.definition.spec.outputSamples.length === 0" class="workflow-inline-empty">尚未添加回显示例</p>
  </section>
</template>
