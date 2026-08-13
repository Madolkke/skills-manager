<script setup lang="ts">
import { CirclePlus, Trash2 } from "lucide-vue-next";
import { ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionDefinition } from "../../../types";
import { parseCliCommandParameters } from "../domain/cliCommandParameters";
import { cloneWorkflow, createWorkflowId } from "../domain/utils";
import { newWorkflowSchema } from "../workflowJsonSchema";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean }>();
const emit = defineEmits<{ change: [definition: CollectionDefinition] }>();
const initialCommand = props.definition.spec.collectionType === "cli" ? props.definition.spec.commandTemplate : "";
const initialParameters = parseCliCommandParameters(initialCommand);
const lastValidParameterNames = ref(initialParameters.error ? [] : initialParameters.names);

watch([() => `${props.definition.id}@${props.definition.revision}`, () => props.definition.spec.collectionType === "cli" ? props.definition.spec.commandTemplate : ""], ([reference], [previousReference]) => {
  const command = props.definition.spec.collectionType === "cli" ? props.definition.spec.commandTemplate : "";
  const parsed = parseCliCommandParameters(command);
  if (!parsed.error) lastValidParameterNames.value = parsed.names;
  else if (reference !== previousReference) lastValidParameterNames.value = [];
});

function update(recipe: (definition: CollectionDefinition) => void): void {
  const definition = cloneWorkflow(props.definition);
  recipe(definition);
  emit("change", definition);
}

function addSample(): void {
  update((definition) => {
    if (definition.spec.collectionType !== "cli") return;
    definition.spec.outputSamples.push({ id: createWorkflowId("sample"), name: `示例 ${definition.spec.outputSamples.length + 1}`, stdout: "", inputValues: {} });
  });
}

function updateCommand(commandTemplate: string): void {
  update((definition) => {
    if (definition.spec.collectionType !== "cli") return;
    const next = parseCliCommandParameters(commandTemplate);
    definition.spec.commandTemplate = commandTemplate;
    definition.spec.commandParameterSyntax = "angle-v1";
    if (next.error) return;

    const nextNames = new Set(next.names);
    const removedNames = new Set(lastValidParameterNames.value.filter((name) => !nextNames.has(name)));
    const removedIds = new Set(definition.inputs.filter((input) => removedNames.has(input.key)).map((input) => input.id));
    definition.inputs = definition.inputs.filter((input) => !removedIds.has(input.id));
    definition.spec.outputSamples.forEach((sample) => removedNames.forEach((name) => delete sample.inputValues[name]));
    next.names.forEach((name) => {
      if (definition.inputs.some((input) => input.key === name)) return;
      definition.inputs.push({
        id: createWorkflowId("collection-input"),
        key: name,
        required: true,
        schema: { ...newWorkflowSchema("string"), title: name },
      });
    });
    lastValidParameterNames.value = next.names;
  });
}
</script>

<template>
  <section class="workflow-field-section" data-workflow-field="spec.commandTemplate" :class="props.definition.spec.collectionType === 'cli' && !props.definition.spec.commandTemplate.trim() && 'field-invalid'">
    <div class="workflow-subhead"><div><h3>采集命令</h3><p>CLI 命令模板，可引用定义中的输入参数。</p></div></div>
    <input
      class="workflow-code-input workflow-command-input"
      type="text"
      spellcheck="false"
      :value="props.definition.spec.collectionType === 'cli' ? props.definition.spec.commandTemplate : ''"
      :disabled="props.readonly"
      @input="updateCommand(($event.target as HTMLInputElement).value)"
    />
  </section>

  <section class="workflow-field-section">
    <div class="workflow-subhead"><div><h3>回显示例</h3><p>{{ props.definition.spec.collectionType === 'cli' ? props.definition.spec.outputSamples.length : 0 }} 个样例</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addSample"><template #icon><CirclePlus /></template>添加</UiButton></div>
    <template v-if="props.definition.spec.collectionType === 'cli'">
      <article v-for="sample in props.definition.spec.outputSamples" :key="sample.id" class="workflow-sample">
        <div><input :value="sample.name" aria-label="样例名称" :disabled="props.readonly" @input="update((definition) => { if (definition.spec.collectionType !== 'cli') return; const target = definition.spec.outputSamples.find((item) => item.id === sample.id); if (target) target.name = ($event.target as HTMLInputElement).value; })" /><UiIconButton label="删除样例" size="sm" variant="danger" :disabled="props.readonly" @click="update((definition) => { if (definition.spec.collectionType === 'cli') definition.spec.outputSamples = definition.spec.outputSamples.filter((item) => item.id !== sample.id); })"><Trash2 /></UiIconButton></div>
        <textarea class="workflow-sample-output" rows="5" spellcheck="false" :value="sample.stdout" :disabled="props.readonly" @input="update((definition) => { if (definition.spec.collectionType !== 'cli') return; const target = definition.spec.outputSamples.find((item) => item.id === sample.id); if (target) target.stdout = ($event.target as HTMLTextAreaElement).value; })" />
      </article>
    </template>
    <p v-if="props.definition.spec.collectionType !== 'cli' || props.definition.spec.outputSamples.length === 0" class="workflow-inline-empty">尚未添加回显示例</p>
  </section>
</template>
